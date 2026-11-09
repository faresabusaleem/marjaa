"""The retrieval pipeline: dense | BM25 | hybrid (RRF) | hybrid + rerank."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from marjaa.config import ChunkStrategy, RetrievalMode, Settings
from marjaa.ingest.pipeline import load_chunks
from marjaa.logging_utils import get_logger
from marjaa.retrieval.indexes import (
    BM25Index,
    DenseIndex,
    NumpyDenseIndex,
    VectorIndex,
    embedding_text,
    fingerprint,
    reciprocal_rank_fusion,
)
from marjaa.retrieval.models import Embedder, Reranker, embedder_for, load_reranker
from marjaa.schemas import Chunk, RetrievedChunk

log = get_logger(__name__)


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    mode: str
    latency_ms: dict[str, float] = field(default_factory=dict)
    # The answer/abstain signal: the best reranker probability, or without a
    # reranker the best dense cosine similarity. BM25 scores are unbounded and
    # not comparable across questions, so BM25 alone gives no signal (None).
    top_relevance: float | None = None


class Retriever:
    def __init__(
        self,
        chunks: list[Chunk],
        settings: Settings,
        embedder: Embedder,
        dense: VectorIndex,
        reranker_loader=None,
    ):
        self.settings = settings
        self.chunks = {c.id: c for c in chunks}
        self.embedder = embedder
        self.dense = dense
        self.bm25 = BM25Index(chunks)
        self._reranker_loader = reranker_loader
        self._reranker: Reranker | None = None

    @property
    def reranker(self) -> Reranker:
        # Loaded lazily: dense/BM25-only experiments never pay for it.
        if self._reranker is None:
            self._reranker = self._reranker_loader()
        return self._reranker

    def get(self, chunk_id: str) -> Chunk | None:
        return self.chunks.get(chunk_id)

    def retrieve(
        self,
        query: str,
        mode: RetrievalMode | None = None,
        top_k: int | None = None,
        language: str | None = None,
    ) -> RetrievalResult:
        """`language` restricts results to one document language (used to test
        cross-lingual retrieval); None searches Arabic and English together."""
        s = self.settings
        mode = mode or s.retrieval_mode
        top_k = top_k or s.top_k
        depth = max(s.candidates_per_retriever, top_k)
        timings: dict[str, float] = {}
        per_stage: dict[str, dict[str, float]] = {}

        lists = []
        if mode in ("dense", "hybrid", "hybrid_rerank"):
            t = time.perf_counter()
            vector = self.embedder.encode_query(query)
            hits = self.dense.search(vector, depth, language)
            timings["dense"] = (time.perf_counter() - t) * 1000
            per_stage["dense"] = dict(hits)
            lists.append(hits)
        if mode in ("bm25", "hybrid", "hybrid_rerank"):
            t = time.perf_counter()
            hits = self.bm25.search(query, depth, language)
            timings["bm25"] = (time.perf_counter() - t) * 1000
            per_stage["bm25"] = dict(hits)
            lists.append(hits)

        ranked = lists[0] if len(lists) == 1 else reciprocal_rank_fusion(lists, s.rrf_k)
        if len(lists) > 1:
            per_stage["rrf"] = dict(ranked)

        if mode == "hybrid_rerank":
            t = time.perf_counter()
            candidates = [cid for cid, _ in ranked[: max(s.rerank_candidates, top_k)]]
            texts = [embedding_text(self.chunks[cid]) for cid in candidates]
            scores = self.reranker.score(query, texts)
            ranked = sorted(zip(candidates, scores, strict=True), key=lambda x: -x[1])
            per_stage["rerank"] = dict(ranked)
            timings["rerank"] = (time.perf_counter() - t) * 1000

        results = [
            RetrievedChunk(
                chunk=self.chunks[cid],
                score=score,
                scores={stage: v[cid] for stage, v in per_stage.items() if cid in v},
            )
            for cid, score in ranked[:top_k]
        ]
        timings["total"] = sum(timings.values())
        signal = per_stage.get("rerank") or per_stage.get("dense")
        relevance = max(signal.values()) if signal else None
        return RetrievalResult(results, mode, timings, relevance)


def collection_name(strategy: str, embedder_name: str) -> str:
    return f"{strategy}_{embedder_name.split('/')[-1]}".replace(".", "_")


def build_retriever(settings: Settings, strategy: ChunkStrategy | None = None) -> Retriever:
    """Load chunks, then load the dense index or (re)build it if chunks changed."""
    strategy = strategy or settings.chunk_strategy
    chunks = load_chunks(settings, strategy)
    embedder = embedder_for(settings)
    collection = collection_name(strategy, embedder.name)
    dense: VectorIndex
    if settings.dense_backend == "numpy":
        dense = NumpyDenseIndex(settings.index_dir, collection)
    else:
        dense = DenseIndex(settings.index_dir / "qdrant", collection)
    fp = fingerprint(chunks, embedder.name)
    if not dense.is_current(fp):
        t = time.perf_counter()
        vectors = embedder.encode([embedding_text(c) for c in chunks])
        dense.build(chunks, vectors, fp)
        log.info("embedded chunks", extra={"n": len(chunks), "s": time.perf_counter() - t})

    def reranker_loader() -> Reranker:
        return load_reranker(
            settings.embedder,
            settings.reranker_model,
            settings.device,
            settings.rerank_max_length,
            settings.rerank_fp16,
        )

    return Retriever(chunks, settings, embedder, dense, reranker_loader)
