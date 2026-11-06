import pytest

from marjaa.config import Settings
from marjaa.ingest.pipeline import run_ingest
from marjaa.retrieval.indexes import reciprocal_rank_fusion
from marjaa.retrieval.retriever import Retriever, build_retriever


@pytest.fixture
def retriever(settings: Settings) -> Retriever:
    run_ingest(settings)
    return build_retriever(settings, "article")


def test_rrf_rewards_agreement() -> None:
    fused = reciprocal_rank_fusion([[("a", 9.0), ("b", 1.0)], [("b", 0.9), ("c", 0.8)]], k=60)
    assert fused[0][0] == "b"  # in both lists
    assert {cid for cid, _ in fused} == {"a", "b", "c"}


@pytest.mark.parametrize("mode", ["dense", "bm25", "hybrid", "hybrid_rerank"])
def test_finds_maternity_article_in_every_mode(retriever: Retriever, mode: str) -> None:
    result = retriever.retrieve("How long is maternity leave?", mode=mode, top_k=3)
    assert result.chunks, mode
    assert 5 in {r.chunk.article for r in result.chunks}
    assert result.latency_ms["total"] >= 0


def test_arabic_query(retriever: Retriever) -> None:
    result = retriever.retrieve("كم مدة الإجازة المرضية؟", mode="bm25", top_k=2)
    assert result.chunks[0].chunk.article == 4
    assert result.chunks[0].chunk.language == "ar"


def test_language_filter(retriever: Retriever) -> None:
    result = retriever.retrieve("sick leave", mode="dense", top_k=5, language="ar")
    assert result.chunks and all(r.chunk.language == "ar" for r in result.chunks)


def test_rerank_exposes_relevance(retriever: Retriever) -> None:
    result = retriever.retrieve("annual leave thirty days", mode="hybrid_rerank", top_k=3)
    assert result.top_relevance is not None and 0 <= result.top_relevance <= 1
    assert {"rrf", "rerank"} <= set(result.chunks[0].scores)


def test_index_is_reused_when_chunks_unchanged(settings: Settings, monkeypatch) -> None:
    run_ingest(settings)
    first = build_retriever(settings, "article")
    calls: list[int] = []
    original = first.embedder.encode

    def counting_encode(texts: list[str]):
        calls.append(len(texts))
        return original(texts)

    monkeypatch.setattr(first.embedder, "encode", counting_encode)
    build_retriever(settings, "article")
    assert calls == []  # second build loads the stored vectors instead of re-embedding
