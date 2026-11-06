"""Shared data models passed between ingestion, retrieval and generation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["ar", "en"]


class LawInfo(BaseModel):
    """One law, as described in `data/raw/laws.toml`."""

    id: str
    name_en: str
    name_ar: str
    type_en: str = ""
    type_ar: str = ""
    number: int | None = None
    year: int | None = None
    source_url: str = ""
    files: dict[Language, str] = Field(default_factory=dict)

    def name(self, lang: Language) -> str:
        return self.name_ar if lang == "ar" else self.name_en


class Page(BaseModel):
    number: int  # 1-based
    text: str


class ParsedDocument(BaseModel):
    law: LawInfo
    language: Language
    source_file: str
    parser: str
    pages: list[Page]
    report: dict = Field(default_factory=dict)  # parser scores, Arabic quality


class Chunk(BaseModel):
    id: str
    law_id: str
    law_name: str  # in the chunk's own language
    law_name_en: str
    law_name_ar: str
    law_number: int | None = None
    law_year: int | None = None
    language: Language
    strategy: Literal["article", "fixed"]
    article: int | None = None  # main article (None for preamble)
    articles: list[int] = Field(default_factory=list)  # every article the chunk touches
    part: int = 0  # sub-chunk index for long articles
    chapter: str = ""
    title: str = ""  # article title, e.g. "Annual leave"
    text: str  # original text, for display and the LLM prompt
    search_text: str  # normalised text (+ context header) used for matching
    source_file: str
    page_start: int
    page_end: int

    @property
    def header(self) -> str:
        """Context prepended to the text for embedding and reranking."""
        return " | ".join(x for x in (self.law_name, self.chapter, self.title) if x)

    @property
    def citation(self) -> str:
        """Canonical citation in the chunk's language."""
        if self.article is None:
            return f"[{self.law_name}]"
        sep, word = ("، ", "المادة") if self.language == "ar" else (", ", "Article")
        return f"[{self.law_name}{sep}{word} {self.article}]"


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float  # final score used for ranking
    scores: dict[str, float] = Field(default_factory=dict)  # per-stage scores
