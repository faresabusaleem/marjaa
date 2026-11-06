"""Two chunking strategies, compared in the evaluation.

- `article_chunks`: one chunk per legal article (long ones sub-split on
  paragraph boundaries). Matches how lawyers cite and gives clean citations.
- `fixed_chunks`: fixed-size character windows with overlap, the common RAG
  baseline. Each window records every article it overlaps, so it can still
  be scored against article-level gold labels.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

from marjaa.ingest.normalize import normalize_for_search, to_ascii_digits
from marjaa.logging_utils import get_logger
from marjaa.schemas import Chunk, Language, ParsedDocument

log = get_logger(__name__)

_ARTICLE_HEADING = {
    # A heading line starts with the word and a number, optionally in brackets,
    # and is short. Cross-references ("Article (30) of this Decree-Law ...")
    # are filtered out by the length check and the sequence check below.
    # Brackets may come out mirrored from RTL-aware PDFs: "Article )2 (".
    "en": re.compile(r"^\s*Article\s*[()\[\]]?\s*(\d{1,3})\s*[()\[\]]?\s*(.{0,60})$", re.I),
    "ar": re.compile(r"^\s*(?:ال)?ماد[ةه]\s*[()\[\]]?\s*([0-9٠-٩]{1,3})\s*[()\[\]]?\s*(.{0,60})$"),
}
_CHAPTER_HEADING = {
    "en": re.compile(r"^\s*(Chapter|Part|Section|Title)\s+[\w\-()]+", re.I),
    "ar": re.compile(r"^\s*(الفصل|الباب|الفرع|القسم)\s+\S+"),
}
_CROSS_REFERENCE = re.compile(r"^(of|from|to|and|or|hereof|من|في|و)\b", re.I)


@dataclass
class ArticleSpan:
    number: int | None  # None = preamble
    start: int
    end: int
    chapter: str


def canonical_heading(line: str, language: Language) -> str:
    """'Article )8 (' -> 'Article (8)', 'المادة (٥)' -> 'المادة (5)'."""
    match = _ARTICLE_HEADING[language].match(line)
    if not match:
        return line
    word = "Article" if language == "en" else "المادة"
    rest = match.group(2).strip()
    return f"{word} ({int(to_ascii_digits(match.group(1)))})" + (f" {rest}" if rest else "")


_LIST_ITEM = re.compile(r"^([0-9٠-٩]+|[a-zأ-ي])\s*[.)\-]")


def article_title(body: str) -> str:
    """The short line right after the heading, e.g. 'Annual leave'."""
    lines = [x.strip() for x in body.split("\n")[1:3] if x.strip()]
    if not lines:
        return ""
    title = lines[0]
    if len(title) > 80 or title.endswith((".", ":", "،", ",")) or _LIST_ITEM.match(title):
        return ""
    return title


class _Document:
    """Full text of a parsed document plus a char-offset -> page lookup."""

    def __init__(self, doc: ParsedDocument):
        self.doc = doc
        self.offsets: list[int] = []
        parts: list[str] = []
        pos = 0
        for page in doc.pages:
            text = "\n".join(
                canonical_heading(line, doc.language) for line in page.text.split("\n")
            )
            self.offsets.append(pos)
            parts.append(text)
            pos += len(text) + 1  # +1 for the joining newline
        self.text = "\n".join(parts)

    def page_at(self, offset: int) -> int:
        idx = max(0, bisect_right(self.offsets, offset) - 1)
        return self.doc.pages[idx].number


def find_articles(text: str, language: Language) -> list[ArticleSpan]:
    """Locate article headings; enforce increasing numbers to reject cross-refs."""
    heading, chapter_re = _ARTICLE_HEADING[language], _CHAPTER_HEADING[language]
    starts: list[tuple[int, int | None, str]] = [(0, None, "")]  # (offset, number, chapter)
    chapter, last, pos = "", 0, 0
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if chapter_re.match(stripped) and len(stripped) < 120:
            chapter = stripped
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt and len(nxt) < 80 and not heading.match(nxt):
                chapter = f"{stripped}: {nxt}"
        match = heading.match(line)
        if match and not _CROSS_REFERENCE.match(match.group(2).strip()):
            number = int(to_ascii_digits(match.group(1)))
            # Accept the next article, tolerating up to 2 missed headings.
            if last < number <= last + 3:
                if number != last + 1:
                    log.warning("article gap", extra={"expected": last + 1, "found": number})
                starts.append((pos, number, chapter))
                last = number
        pos += len(line) + 1
    spans = []
    for (start, number, chap), nxt in zip(
        starts, [*starts[1:], (len(text), None, "")], strict=True
    ):
        if text[start : nxt[0]].strip():
            spans.append(ArticleSpan(number, start, nxt[0], chap))
    return spans


def _strip_chapter_lines(body: str, language: Language) -> str:
    """Chapter headings sit between articles; keep them out of article bodies."""
    lines = body.split("\n")
    chapter_re = _CHAPTER_HEADING[language]
    keep: list[str] = []
    skip_next = False
    for line in lines:
        if skip_next:
            skip_next = False
            if len(line.strip()) < 80 and not _ARTICLE_HEADING[language].match(line):
                continue
        if chapter_re.match(line.strip()) and len(line.strip()) < 120:
            skip_next = True
            continue
        keep.append(line)
    return "\n".join(keep).strip()


def _pack_paragraphs(text: str, max_chars: int) -> list[str]:
    """Greedy packing of paragraphs into parts of at most `max_chars`."""
    paragraphs = [p for p in text.split("\n") if p.strip()]
    parts, current = [], ""
    for para in paragraphs:
        while len(para) > max_chars:  # a single huge paragraph: hard split on spaces
            cut = para.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            if current:
                parts.append(current)
                current = ""
            parts.append(para[:cut])
            para = para[cut:].strip()
        if current and len(current) + len(para) + 1 > max_chars:
            parts.append(current)
            current = para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        parts.append(current)
    return parts


def _make_chunk(
    doc: ParsedDocument, cid: str, strategy: str, text: str, chapter: str, **kw: object
) -> Chunk:
    law, lang = doc.law, doc.language
    title = str(kw.get("title", ""))
    header = " | ".join(x for x in (law.name(lang), chapter, title) if x)
    return Chunk(
        id=cid,
        law_id=law.id,
        law_name=law.name(lang),
        law_name_en=law.name_en,
        law_name_ar=law.name_ar,
        law_number=law.number,
        law_year=law.year,
        language=lang,
        strategy=strategy,  # type: ignore[arg-type]
        chapter=chapter,
        text=text,
        # A short context header (law, chapter, article title) helps both BM25
        # and dense retrieval, especially for sub-split parts of long articles.
        search_text=normalize_for_search(f"{header}\n{text}"),
        source_file=doc.source_file,
        **kw,  # type: ignore[arg-type]
    )


def article_chunks(doc: ParsedDocument, max_chars: int = 2500) -> list[Chunk]:
    full = _Document(doc)
    chunks: list[Chunk] = []
    for span in find_articles(full.text, doc.language):
        body = _strip_chapter_lines(full.text[span.start : span.end], doc.language)
        if not body:
            continue
        pages = {"page_start": full.page_at(span.start), "page_end": full.page_at(span.end - 1)}
        if span.number is None:
            cid = f"{doc.law.id}-{doc.language}-preamble"
            chunks.append(_make_chunk(doc, cid, "article", body, "", **pages))
            continue
        title = article_title(body)
        lines = body.split("\n")
        head_lines = 2 if title else 1  # heading (+ title) is repeated on every part
        head = "\n".join(lines[:head_lines])
        rest = "\n".join(lines[head_lines:])
        parts = [body] if len(body) <= max_chars else _pack_paragraphs(rest, max_chars - len(head))
        for i, part in enumerate(parts):
            text = part if len(parts) == 1 else f"{head}\n{part}"
            chunks.append(
                _make_chunk(
                    doc,
                    f"{doc.law.id}-{doc.language}-a{span.number:03d}-p{i}",
                    "article",
                    text,
                    span.chapter,
                    article=span.number,
                    articles=[span.number],
                    part=i,
                    title=title,
                    **pages,
                )
            )
    return chunks


def fixed_chunks(doc: ParsedDocument, size: int = 1200, overlap: int = 200) -> list[Chunk]:
    full = _Document(doc)
    spans = [s for s in find_articles(full.text, doc.language) if s.number is not None]
    titles = {s.number: article_title(full.text[s.start : s.end]) for s in spans}
    text, chunks, start, i = full.text, [], 0, 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):  # snap to a word boundary so words are not cut
            space = text.rfind(" ", start + size // 2, end)
            end = space if space > 0 else end
        window = text[start:end].strip()
        if window:
            overlaps = [(min(end, s.end) - max(start, s.start), s) for s in spans]
            touched = [(n, s) for n, s in overlaps if n > 0]
            main = max(touched, key=lambda t: t[0])[1] if touched else None
            chunks.append(
                _make_chunk(
                    doc,
                    f"{doc.law.id}-{doc.language}-f{i:04d}",
                    "fixed",
                    window,
                    main.chapter if main else "",
                    article=main.number if main else None,
                    articles=[s.number for _, s in touched if s.number is not None],
                    title=titles.get(main.number, "") if main else "",
                    page_start=full.page_at(start),
                    page_end=full.page_at(max(start, end - 1)),
                )
            )
            i += 1
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks
