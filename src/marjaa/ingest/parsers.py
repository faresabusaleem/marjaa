"""PDF / HTML parsing with an automatic Arabic text-quality check.

Arabic PDF extraction often goes wrong in four ways:
1. Letters come out in *visual* order, so words read backwards (ةداملا).
2. Glyphs come out as "presentation forms" (ﺍﻟﻤﺎﺩﺓ) instead of letters.
3. The lam-alef ligature is decomposed in the wrong order (عالقات for علاقات).
4. Words break into isolated letters separated by spaces.
`text_quality` measures all four. With `parser="auto"` every installed parser
is tried and the cleanest Arabic output wins; on the UAE Labour Law PDF this
picks pypdf (PyMuPDF breaks lam-alef, pdfplumber reverses the text).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from marjaa.ingest.normalize import clean_text, normalize_for_search
from marjaa.logging_utils import get_logger
from marjaa.schemas import Page

log = get_logger(__name__)

# Very frequent words in Arabic legal text (normalised form).
_COMMON_AR = {
    normalize_for_search(w)
    for w in (
        "في من على الى أو أن التي الذي المادة العمل العامل صاحب هذا هذه وفقا القانون لا"
    ).split()
}
_AR_LETTERS = "ء-ي"
_AR_WORD = re.compile(f"[{_AR_LETTERS}]+")
_ARABIC_ANY = re.compile("[؀-ۿﭐ-﷿ﹰ-ﻼ]")
_PRESENTATION_FORMS = re.compile("[ﭐ-﷿ﹰ-ﻼ]")
# Correct Arabic never starts a word with these; a swapped lam-alef does
# (اإلمارات for الإمارات, اال for الا, امل for الم).
_LIGATURE_ERROR = re.compile("(?:^|\\s)(?:اإل|األ|اال|امل)")


@dataclass
class Quality:
    common_word_rate: float  # share of Arabic tokens that are common words
    reversed_word_rate: float  # same, but for tokens read backwards
    presentation_form_rate: float
    ligature_error_rate: float  # swapped lam-alef per Arabic word
    mean_word_len: float

    @property
    def score(self) -> float:
        """Higher is better. Penalises reversed text and broken letters/words."""
        broken = 1.0 if self.mean_word_len < 2.5 else 0.0
        return (
            self.common_word_rate
            - self.reversed_word_rate
            - self.presentation_form_rate
            - 5 * self.ligature_error_rate
            - broken
        )

    @property
    def looks_reversed(self) -> bool:
        return self.reversed_word_rate > self.common_word_rate


def text_quality(raw_text: str) -> Quality:
    """Score *raw* extracted text (before any cleanup)."""
    letters = max(1, len(_ARABIC_ANY.findall(raw_text)))
    pres = len(_PRESENTATION_FORMS.findall(raw_text)) / letters
    words = _AR_WORD.findall(normalize_for_search(raw_text))
    if not words:
        return Quality(0.0, 0.0, pres, 0.0, 0.0)
    forward = sum(w in _COMMON_AR for w in words) / len(words)
    backward = sum(w[::-1] in _COMMON_AR for w in words) / len(words)
    ligature = len(_LIGATURE_ERROR.findall(raw_text)) / len(words)
    mean_len = sum(map(len, words)) / len(words)
    return Quality(forward, backward, pres, ligature, mean_len)


def fix_reversed_line(line: str) -> str:
    """Undo visual ordering: reverse the line, then re-reverse digit/Latin runs."""
    flipped = line[::-1]
    return re.sub(r"[0-9A-Za-z.,/%-]+", lambda m: m.group(0)[::-1], flipped)


_LEADING_PUNCT = re.compile(f"(^|\\s)([.:،؛])(?=[{_AR_LETTERS}])")


def fix_arabic_punctuation(line: str) -> str:
    """RTL extraction often puts a sentence's final '.' or ':' *before* its
    first word ('.تحمل تكاليف ...'). Move it back to the end of the line."""
    match = _LEADING_PUNCT.search(line)
    if not match:
        return line
    punct = match.group(2)
    fixed = line[: match.start(2)] + line[match.end(2) :]
    return fixed.rstrip() + punct


# --- Parsers ------------------------------------------------------------------


def _pypdf(path: Path) -> list[Page]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return [Page(number=i + 1, text=p.extract_text() or "") for i, p in enumerate(reader.pages)]


def _pymupdf(path: Path) -> list[Page]:
    import pymupdf

    with pymupdf.open(path) as doc:
        return [Page(number=i + 1, text=p.get_text("text")) for i, p in enumerate(doc)]


def _pdfplumber(path: Path) -> list[Page]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return [Page(number=i + 1, text=p.extract_text() or "") for i, p in enumerate(pdf.pages)]


PDF_PARSERS: dict[str, Callable[[Path], list[Page]]] = {
    "pypdf": _pypdf,
    "pymupdf": _pymupdf,
    "pdfplumber": _pdfplumber,
}


def parse_html(path: Path) -> list[Page]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    root = soup.find("main") or soup.body or soup
    return [Page(number=1, text=root.get_text("\n"))]


_EDGE_NUMBER = re.compile(r"^\s*\d+\s*|\s*\d+\s*$")
_PAGE_NUMBER = re.compile(r"^[\d٠-٩\s/\-–]+$|^(page|صفحة)\s*\d+", re.IGNORECASE)


def _header_key(line: str) -> str:
    # Running headers often carry the page number ("... Labour Relations 3").
    return _EDGE_NUMBER.sub("", line.strip())


def remove_repeated_lines(pages: list[Page], min_share: float = 0.5) -> list[Page]:
    """Drop running headers/footers: (long) lines that repeat on most pages."""
    if len(pages) < 4:
        return pages
    counts: Counter[str] = Counter()
    for page in pages:
        keys = {_header_key(line) for line in page.text.splitlines()}
        counts.update(k for k in keys if len(k) >= 20)
    repeated = {key for key, n in counts.items() if n / len(pages) >= min_share}
    cleaned = []
    for page in pages:
        kept = [
            line
            for line in page.text.splitlines()
            if _header_key(line) not in repeated and not _PAGE_NUMBER.match(line.strip())
        ]
        cleaned.append(Page(number=page.number, text="\n".join(kept)))
    return cleaned


def _extract(path: Path, language: str, parser: str) -> tuple[list[Page], str, dict]:
    if parser != "auto":
        pages = PDF_PARSERS[parser](path)
        return pages, parser, {}
    if language != "ar":
        return PDF_PARSERS["pypdf"](path), "pypdf", {}
    results: dict[str, tuple[list[Page], Quality]] = {}
    for name, fn in PDF_PARSERS.items():
        try:
            pages = fn(path)
        except ImportError:
            continue  # optional parser not installed
        results[name] = (pages, text_quality("\n".join(p.text for p in pages)))
    best = max(results, key=lambda n: results[n][1].score)
    scores = {n: round(q.score, 4) for n, (_, q) in results.items()}
    log.info("parser comparison", extra={"file": path.name, "scores": scores, "chosen": best})
    return results[best][0], best, scores


def parse_file(path: Path, language: str, parser: str = "auto") -> tuple[list[Page], str, dict]:
    """Parse a file into cleaned pages. Returns (pages, parser_name, report)."""
    report: dict = {}
    if path.suffix.lower() in {".html", ".htm"}:
        pages, parser = parse_html(path), "html"
    else:
        pages, parser, report["parser_scores"] = _extract(path, language, parser)

    if language == "ar":
        quality = text_quality("\n".join(p.text for p in pages))
        report["quality"] = asdict(quality) | {"score": round(quality.score, 4)}
        log.info("arabic extraction quality", extra={"file": path.name, "parser": parser})
        if quality.looks_reversed:
            log.warning("text looks visually ordered; reversing lines", extra={"file": path.name})
            pages = [
                Page(
                    number=p.number,
                    text="\n".join(fix_reversed_line(x) for x in p.text.splitlines()),
                )
                for p in pages
            ]
        elif quality.score < 0.05:
            raise ValueError(
                f"{path.name}: Arabic text extracted by {parser} looks unreadable "
                f"({quality}). Try another parser: {list(PDF_PARSERS)}"
            )
        pages = [
            Page(
                number=p.number,
                text="\n".join(fix_arabic_punctuation(x) for x in p.text.splitlines()),
            )
            for p in pages
        ]

    pages = [Page(number=p.number, text=clean_text(p.text)) for p in pages]
    return remove_repeated_lines(pages), parser, report
