"""Parse citations out of an answer and check each one against the sources.

An LLM can cite an article that was never retrieved (a hallucinated
citation). We parse every `[Law, Article N]` / `[القانون، المادة N]` and
mark it valid only if a retrieved chunk really is that law and article.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from marjaa.ingest.normalize import normalize_for_search, to_ascii_digits
from marjaa.schemas import Chunk

# [<law name>, Article 30]  [<law name>, Articles 30 and 31]  [<اسم القانون>، المادة (30)]
CITATION_RE = re.compile(
    r"\[\s*([^\[\]]{2,150}?)\s*[,،]\s*"
    r"(?:Articles?|Art\.?|المادتين|المادتان|المواد|المادة|مادة)\s*"
    r"([^\[\]]{1,40}?)\s*\]"
)
_NUMBER = re.compile(r"[0-9٠-٩]{1,3}")
_SENTENCE = re.compile(r"(?<=[.!?؟])\s+|\n+")


class Citation(BaseModel):
    text: str  # as written in the answer
    law_id: str | None  # None if the law name matched no known law
    article: int
    valid: bool  # True if a retrieved chunk is this law + article
    chunk_id: str | None = None


def _resolve_law(name: str, chunks: list[Chunk]) -> str | None:
    norm = normalize_for_search(name)
    for c in chunks:
        for candidate in (c.law_name_en, c.law_name_ar, c.law_id):
            cand = normalize_for_search(candidate)
            if cand and (cand in norm or norm in cand):
                return c.law_id
    return None


def extract_citations(answer: str, sources: list[Chunk]) -> list[Citation]:
    citations: list[Citation] = []
    for match in CITATION_RE.finditer(answer):
        law_id = _resolve_law(match.group(1), sources)
        for num in _NUMBER.findall(match.group(2)):
            article = int(to_ascii_digits(num))
            chunk = next((c for c in sources if c.law_id == law_id and article in c.articles), None)
            citations.append(
                Citation(
                    text=match.group(0),
                    law_id=law_id,
                    article=article,
                    valid=chunk is not None,
                    chunk_id=chunk.id if chunk else None,
                )
            )
    return citations


def citation_coverage(answer: str) -> float:
    """Share of substantive sentences that carry at least one citation."""
    sentences = [s for s in _SENTENCE.split(answer) if len(s.strip()) > 25]
    if not sentences:
        return 0.0
    cited = sum(bool(CITATION_RE.search(s)) for s in sentences)
    return cited / len(sentences)


def is_not_found(answer: str) -> bool:
    """Did the model abstain? Tolerates small wording/punctuation differences."""
    norm = normalize_for_search(answer)
    markers = (
        "not found in the provided laws",
        normalize_for_search("لم يتم العثور على إجابة"),
        normalize_for_search("لم يتم العثور على اجابة"),
    )
    return any(m in norm for m in markers) and len(norm) < 220
