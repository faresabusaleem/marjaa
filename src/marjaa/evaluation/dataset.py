"""The evaluation test set: questions with gold articles and reference answers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from marjaa.evaluation.metrics import ArticleKey
from marjaa.schemas import Language

QuestionType = Literal["ar", "en", "cross_ar_en", "cross_en_ar", "multi", "unanswerable"]


class GoldRef(BaseModel):
    law_id: str
    article: int


class EvalItem(BaseModel):
    id: str
    type: QuestionType
    question: str
    question_lang: Language
    # Restrict retrieval to documents in this language. Set for cross-lingual
    # items (e.g. an Arabic question that must be answered from the English
    # text) so the test cannot be passed by matching the same-language copy.
    search_lang: Language | None = None
    gold: list[GoldRef] = Field(default_factory=list)  # empty = not answerable
    reference_answer: str = ""
    source_text_lang: Language | None = None
    split: Literal["dev", "test"] = "test"

    @property
    def answerable(self) -> bool:
        return bool(self.gold)

    @property
    def gold_keys(self) -> set[ArticleKey]:
        return {(g.law_id, g.article) for g in self.gold}


def load_testset(path: Path) -> list[EvalItem]:
    with path.open(encoding="utf-8") as f:
        return [EvalItem.model_validate_json(line) for line in f if line.strip()]


def save_testset(path: Path, items: list[EvalItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(item.model_dump_json() + "\n")
