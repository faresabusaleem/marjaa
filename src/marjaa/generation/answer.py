"""End-to-end answering: retrieve -> gate on confidence -> prompt -> stream -> verify."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from marjaa.config import Settings
from marjaa.generation.citations import (
    Citation,
    citation_coverage,
    extract_citations,
    is_not_found,
)
from marjaa.generation.prompts import (
    CONDENSE_SYSTEM,
    NOT_FOUND,
    citation_for,
    condense_prompt,
    system_prompt,
    user_prompt,
)
from marjaa.generation.providers import LLMProvider, generate
from marjaa.ingest.normalize import detect_language
from marjaa.logging_utils import get_logger
from marjaa.retrieval.retriever import Retriever
from marjaa.schemas import Language, RetrievedChunk
from marjaa.tracing import new_trace_id, save_trace

log = get_logger(__name__)


class Source(BaseModel):
    """What the API/UI shows for each retrieved chunk."""

    id: str
    citation: str
    law_name: str
    article: int | None
    language: Language
    page_start: int
    page_end: int
    score: float
    text: str


class Turn(BaseModel):
    """One earlier question and answer, sent back by the UI for follow-ups."""

    question: str = Field(max_length=1000)
    answer: str = Field(max_length=4000)


class AnswerResult(BaseModel):
    trace_id: str
    question: str
    # The standalone question actually searched and answered (differs from
    # `question` only for follow-ups).
    search_query: str | None = None
    language: Language
    answer: str
    abstained: bool
    abstain_reason: Literal["low_relevance", "model"] | None = None
    top_relevance: float | None = None
    citations: list[Citation] = Field(default_factory=list)
    citation_coverage: float = 0.0
    sources: list[Source] = Field(default_factory=list)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    provider: str = ""
    model: str = ""

    @property
    def all_citations_valid(self) -> bool:
        return all(c.valid for c in self.citations)


def select_context(retrieved: list[RetrievedChunk], lang: Language, k: int) -> list[RetrievedChunk]:
    """Keep the top-k *distinct* passages.

    Arabic and English copies of the same article often both rank highly;
    sending both wastes context, so keep one copy, preferring the question's
    language (the model then quotes wording the user can read).
    """

    def key(r: RetrievedChunk) -> tuple:
        c = r.chunk
        return (c.law_id, c.article, c.part) if c.strategy == "article" else (c.id,)

    chosen: dict[tuple, RetrievedChunk] = {}
    order: list[tuple] = []
    for r in retrieved:
        k_ = key(r)
        if k_ not in chosen:
            chosen[k_] = r
            order.append(k_)
        elif r.chunk.language == lang and chosen[k_].chunk.language != lang:
            chosen[k_] = r  # same article, better language, keep the higher rank slot
    return [chosen[k_] for k_ in order[:k]]


def to_source(r: RetrievedChunk, lang: Language) -> Source:
    c = r.chunk
    return Source(
        id=c.id,
        citation=citation_for(c, lang),
        law_name=c.law_name,
        article=c.article,
        language=c.language,
        page_start=c.page_start,
        page_end=c.page_end,
        score=r.score,
        text=c.text,
    )


class RagPipeline:
    def __init__(self, retriever: Retriever, provider: LLMProvider, settings: Settings):
        self.retriever = retriever
        self.provider = provider
        self.settings = settings

    def condense(self, question: str, history: list[Turn]) -> str:
        """Rewrite a follow-up into a standalone question (one short LLM call)."""
        pairs = [(t.question, t.answer) for t in history[-3:]]
        raw = generate(self.provider, CONDENSE_SYSTEM, condense_prompt(question, pairs))
        lines = [x.strip().strip('"«»') for x in raw.strip().splitlines() if x.strip()]
        rewritten = lines[0] if lines else ""
        # Guard against a rambling reply: fall back to the user's own words.
        return rewritten if 0 < len(rewritten) <= 3 * len(question) + 300 else question

    def stream(self, question: str, history: list[Turn] | None = None) -> Iterator[dict[str, Any]]:
        """Yields {"event": "sources"|"token"|"done", "data": ...} dicts."""
        s = self.settings
        t_start = time.perf_counter()
        trace_id = new_trace_id()
        lang: Language = detect_language(question)  # type: ignore[assignment]
        latency: dict[str, float] = {}

        query = question
        if history:
            query = self.condense(question, history)
            latency["rewrite"] = (time.perf_counter() - t_start) * 1000

        t_retrieval = time.perf_counter()
        result = self.retriever.retrieve(query, top_k=s.top_k * 2)
        context = select_context(result.chunks, lang, s.top_k)
        sources = [to_source(r, lang) for r in context]
        latency["retrieval"] = (time.perf_counter() - t_retrieval) * 1000
        yield {
            "event": "sources",
            "data": {
                "trace_id": trace_id,
                "language": lang,
                "search_query": query if query != question else None,
                "sources": [x.model_dump() for x in sources],
            },
        }

        top = result.top_relevance
        system = user = ""
        threshold = s.min_relevance or 0.0
        if not context or (top is not None and top < threshold):
            # Low retrieval confidence: abstain without calling the LLM at all.
            answer, reason = NOT_FOUND[lang], "low_relevance"
            yield {"event": "token", "data": {"text": answer}}
        else:
            chunks = [r.chunk for r in context]
            system = system_prompt(lang, citation_for(chunks[0], lang))
            user = user_prompt(query, chunks, lang)
            parts: list[str] = []
            t_gen = time.perf_counter()
            for token in self.provider.stream(system, user):
                if not parts:
                    latency["first_token"] = (time.perf_counter() - t_start) * 1000
                parts.append(token)
                yield {"event": "token", "data": {"text": token}}
            latency["generation"] = (time.perf_counter() - t_gen) * 1000
            answer = "".join(parts).strip()
            reason = "model" if is_not_found(answer) else None

        citations = extract_citations(answer, [r.chunk for r in context]) if not reason else []
        latency["total"] = (time.perf_counter() - t_start) * 1000
        final = AnswerResult(
            trace_id=trace_id,
            question=question,
            search_query=query if query != question else None,
            language=lang,
            answer=answer,
            abstained=reason is not None,
            abstain_reason=reason,  # type: ignore[arg-type]
            top_relevance=top,
            citations=citations,
            citation_coverage=citation_coverage(answer) if not reason else 0.0,
            sources=sources,
            latency_ms=latency,
            provider=self.provider.name,
            model=self.provider.model,
        )
        if s.save_traces:
            save_trace(
                s.traces_dir,
                trace_id,
                {
                    **final.model_dump(exclude={"sources"}),
                    "retrieval": {
                        "mode": result.mode,
                        "latency_ms": result.latency_ms,
                        "candidates": [
                            {"id": r.chunk.id, "score": r.score, "scores": r.scores}
                            for r in result.chunks
                        ],
                        "context_ids": [r.chunk.id for r in context],
                    },
                    "prompt": {"system": system, "user": user},
                },
            )
        log.info(
            "answered",
            extra={
                "trace_id": trace_id,
                "lang": lang,
                "abstained": final.abstained,
                "n_citations": len(citations),
                "invalid_citations": sum(not c.valid for c in citations),
                "latency_ms": round(latency["total"]),
            },
        )
        yield {"event": "done", "data": final.model_dump(exclude={"sources"})}

    def answer(self, question: str, history: list[Turn] | None = None) -> AnswerResult:
        sources: list[dict[str, Any]] = []
        done: dict[str, Any] = {}
        for event in self.stream(question, history):
            if event["event"] == "sources":
                sources = event["data"]["sources"]
            elif event["event"] == "done":
                done = event["data"]
        return AnswerResult(**done, sources=[Source(**x) for x in sources])
