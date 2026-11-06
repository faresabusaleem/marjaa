"""PDF / HTML parsing with an automatic Arabic text-quality check.

Arabic PDF extraction often goes wrong in three ways:
1. Letters come out in *visual* order, so words read backwards (ةداملا).
2. Glyphs come out as "presentation forms" (ﺍﻟﻤﺎﺩﺓ) instead of letters.
3. Words break into isolated letters separated by spaces.
`text_quality` measures all three so we can compare parsers objectively and
refuse to index unreadable text.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from marjaa.ingest.normalize import clean_text, normalize_for_search
from marjaa.logging_utils import get_logger
from marjaa.schemas import Page

log = get_logger(__name__)

# Very frequent words in Arabic legal text (normalised form).
_COMMON_AR = {
    normalize_for_search(w)
    for w in [
        "في",
        "من",
        "على",
        "الى",
        "أو",
        "أن",
        "التي",
        "الذي",
        "المادة",
        "العمل",
        "العامل",
        "صاحب",
        "هذا",
        "هذه",
        "وفقا",
        "القانون",
        "لا",
    ]
}
_AR_WORD = re.compile(r"[ء-ي]+")
_PRESENTATION_FORMS = re.compile(r"[ﭐ-﷿ﹰ-﻿]")


@dataclass
class Quality:
    common_word_rate: float  # share of Arabic tokens that are common words
    reversed_word_rate: float  # same, but for tokens read backwards
    presentation_form_rate: float
    mean_word_len: float

    @property
    def score(self) -> float:
        """Higher is better. Penalises reversed text and broken words."""
        broken = 1.0 if self.mean_word_len < 2.5 else 0.0
        return (
            self.common_word_rate - self.reversed_word_rate - self.presentation_form_rate - broken
        )

    @property
    def looks_reversed(self) -> bool:
        return self.reversed_word_rate > self.common_word_rate


def text_quality(raw_text: str) -> Quality:
    """Score *raw* extracted text (before any cleanup)."""
    letters = max(1, len(re.findall(r"[؀-ۿﭐ-﻿]", raw_text)))
    pres = len(_PRESENTATION_FORMS.findall(raw_text)) / letters
    words = _AR_WORD.findall(normalize_for_search(raw_text))
    if not words:
        return Quality(0.0, 0.0, pres, 0.0)
    forward = sum(w in _COMMON_AR for w in words) / len(words)
    backward = sum(w[::-1] in _COMMON_AR for w in words) / len(words)
    mean_len = sum(map(len, words)) / len(words)
    return Quality(forward, backward, pres, mean_len)


def fix_reversed_line(line: str) -> str:
    """Undo visual ordering: reverse the line, then re-reverse digit/Latin runs."""
    flipped = line[::-1]
    return re.sub(r"[0-9A-Za-z.,/%-]+", lambda m: m.group(0)[::-1], flipped)


# --- Parsers ------------------------------------------------------------------


def _pymupdf(path: Path) -> list[Page]:
    import pymupdf

    with pymupdf.open(path) as doc:
        return [Page(number=i + 1, text=p.get_text("text")) for i, p in enumerate(doc)]


def _pdfplumber(path: Path) -> list[Page]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return [Page(number=i + 1, text=p.extract_text() or "") for i, p in enumerate(pdf.pages)]


def _pypdf(path: Path) -> list[Page]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return [Page(number=i + 1, text=p.extract_text() or "") for i, p in enumerate(reader.pages)]


PDF_PARSERS: dict[str, Callable[[Path], list[Page]]] = {
    "pymupdf": _pymupdf,
    "pdfplumber": _pdfplumber,
    "pypdf": _pypdf,
}


def parse_html(path: Path) -> list[Page]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    root = soup.find("main") or soup.body or soup
    return [Page(number=1, text=root.get_text("\n"))]


def remove_repeated_lines(pages: list[Page], min_share: float = 0.5) -> list[Page]:
    """Drop running headers/footers: lines that repeat on most pages."""
    if len(pages) < 4:
        return pages
    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({line.strip() for line in page.text.splitlines() if line.strip()})
    repeated = {line for line, n in counts.items() if n / len(pages) >= min_share}
    page_number = re.compile(r"^[\d٠-٩\s/\-–]+$|^(page|صفحة)\s*\d+", re.IGNORECASE)
    cleaned = []
    for page in pages:
        kept = [
            line
            for line in page.text.splitlines()
            if line.strip() not in repeated and not page_number.match(line.strip())
        ]
        cleaned.append(Page(number=page.number, text="\n".join(kept)))
    return cleaned


def parse_file(path: Path, language: str, parser: str = "pymupdf") -> tuple[list[Page], str]:
    """Parse a file into cleaned pages. Returns (pages, parser_name)."""
    if path.suffix.lower() in {".html", ".htm"}:
        pages, parser = parse_html(path), "html"
    else:
        pages = PDF_PARSERS[parser](path)

    raw = "\n".join(p.text for p in pages)
    if language == "ar":
        quality = text_quality(raw)
        log.info(
            "arabic extraction quality",
            extra={"file": path.name, "parser": parser, **vars(quality)},
        )
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

    pages = [Page(number=p.number, text=clean_text(p.text)) for p in pages]
    return remove_repeated_lines(pages), parser
