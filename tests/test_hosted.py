"""The hosted profile: Gemini embeddings (mocked here), numpy index, /api routes."""

import json

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from marjaa.api import app as api_module
from marjaa.api.app import create_app, pipeline_dep
from marjaa.config import HOSTED_DIR, Settings
from marjaa.generation.answer import RagPipeline, Turn
from marjaa.generation.providers import FakeProvider, RetryableError
from marjaa.ingest.pipeline import load_chunks, run_ingest
from marjaa.retrieval.indexes import NumpyDenseIndex, fingerprint
from marjaa.retrieval.models import GeminiEmbedder
from marjaa.retrieval.retriever import build_retriever, collection_name
from marjaa.schemas import Chunk


def test_hosted_profile_defaults_and_overrides() -> None:
    s = Settings(profile="hosted", _env_file=None)
    assert (s.embedder, s.dense_backend, s.retrieval_mode, s.llm_provider) == (
        "gemini",
        "numpy",
        "hybrid",
        "gemini",
    )
    assert s.threshold_file == HOSTED_DIR / "threshold.json" and not s.save_traces
    # Anything set explicitly still wins over the profile.
    assert (
        Settings(profile="hosted", retrieval_mode="dense", _env_file=None).retrieval_mode == "dense"
    )
    assert Settings(_env_file=None).embedder == "bge-m3"


def test_gemini_embedder_request_format_batching_and_cache() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"
        assert request.url.path.endswith("/models/gemini-embedding-2:batchEmbedContents")
        body = json.loads(request.content)
        calls.append(body)
        values = [3.0, 4.0] + [0.0] * 6  # norm 5, so normalising must kick in
        return httpx.Response(
            200, json={"embeddings": [{"values": values}] * len(body["requests"])}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    embedder = GeminiEmbedder("gemini-embedding-2", 8, "test-key", client=client)
    embedder.BATCH = 2
    docs = embedder.encode(["Labour Law, Article 29\nAnnual leave text", "b\nc", "d\ne"])
    assert docs.shape == (3, 8) and np.allclose(np.linalg.norm(docs, axis=1), 1.0)
    assert len(calls) == 2  # 3 documents in batches of 2
    first = calls[0]["requests"][0]
    assert first["content"]["parts"][0]["text"] == (
        "title: Labour Law, Article 29 | text: Annual leave text"
    )
    assert first["output_dimensionality"] == 8 and first["model"] == "models/gemini-embedding-2"

    embedder.encode_query("annual leave")
    embedder.encode_query("annual leave")  # served from the cache
    assert len(calls) == 3
    assert calls[2]["requests"][0]["content"]["parts"][0]["text"] == (
        "task: search result | query: annual leave"
    )
    embedder.clear_cache()  # latency runs clear it so every mode pays for its API call
    embedder.encode_query("annual leave")
    assert len(calls) == 4


def _chunk(cid: str, lang: str) -> Chunk:
    return Chunk(
        id=cid, law_id="l", law_name="L", law_name_en="L", law_name_ar="ل", law_number=1,
        law_year=2021, language=lang, strategy="article", article=1, articles=[1], part=0,
        chapter="", title="", text="t", search_text="t", source_file="x.pdf", page_start=1,
        page_end=1,
    )  # fmt: skip


def test_numpy_index_search_language_filter_and_reload(tmp_path) -> None:
    chunks = [_chunk("a", "en"), _chunk("b", "ar"), _chunk("c", "en")]
    vectors = np.eye(3, dtype=np.float32)
    index = NumpyDenseIndex(tmp_path, "article_test")
    assert not index.is_current("fp")
    index.build(chunks, vectors, "fp")
    assert index.search(np.array([0, 1, 0.5]), 2) == [("b", 1.0), ("c", 0.5)]
    assert [cid for cid, _ in index.search(np.array([0, 1, 0.5]), 3, "en")] == ["c", "a"]
    reloaded = NumpyDenseIndex(tmp_path, "article_test")
    assert reloaded.is_current("fp") and not reloaded.is_current("other")


def test_numpy_backend_gives_dense_relevance_without_reranker(settings: Settings) -> None:
    settings = settings.model_copy(update={"dense_backend": "numpy"})
    run_ingest(settings)
    retriever = build_retriever(settings)
    hybrid = retriever.retrieve("maternity leave", mode="hybrid")
    assert hybrid.top_relevance is not None and 0 < hybrid.top_relevance <= 1.0001
    assert retriever.retrieve("maternity leave", mode="bm25").top_relevance is None


class _Rewriter(FakeProvider):
    def stream(self, system: str, prompt: str):
        if "standalone" in system:
            yield "How many days of maternity leave does a female worker get?"
            return
        yield from super().stream(system, prompt)


def test_follow_up_is_rewritten_before_search(settings: Settings) -> None:
    run_ingest(settings)
    pipeline = RagPipeline(build_retriever(settings), _Rewriter(), settings)
    history = [Turn(question="How long is sick leave?", answer="90 days [Labour Law, Article 2].")]
    result = pipeline.answer("and maternity?", history)
    assert result.search_query == "How many days of maternity leave does a female worker get?"
    assert "rewrite" in result.latency_ms and result.question == "and maternity?"
    assert any("maternity" in s.text.lower() for s in result.sources)
    assert pipeline.answer("How long is sick leave?").search_query is None


@pytest.fixture
def pipeline(settings: Settings) -> RagPipeline:
    run_ingest(settings)
    return RagPipeline(build_retriever(settings), FakeProvider(), settings)


def test_api_only_app_serves_under_api_prefix(pipeline: RagPipeline) -> None:
    app = create_app(preload=False, api_only=True)
    app.dependency_overrides[pipeline_dep] = lambda: pipeline
    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/health").status_code == 404
    resp = client.post("/api/ask?stream=false", json={"question": "maternity leave", "history": []})
    assert resp.status_code == 200 and resp.json()["sources"]


def test_stream_ends_with_error_event_when_llm_is_busy(pipeline: RagPipeline) -> None:
    class Busy(FakeProvider):
        def stream(self, system: str, prompt: str):
            raise RetryableError(429)
            yield  # pragma: no cover

    pipeline.provider = Busy()
    app = create_app(preload=False)
    app.dependency_overrides[pipeline_dep] = lambda: pipeline
    body = TestClient(app).post("/api/ask", json={"question": "maternity leave"}).text
    assert "event: sources" in body
    last = body.strip().split("\n\n")[-1]
    assert last.startswith("event: error") and '"code": "busy"' in last


def test_missing_key_is_a_503_not_a_crash(monkeypatch) -> None:
    def no_key():
        raise ValueError("GEMINI_API_KEY is not set (put it in .env)")

    monkeypatch.setattr(api_module, "get_pipeline", no_key)
    resp = TestClient(create_app(preload=False, api_only=True)).get("/api/health")
    assert resp.status_code == 503 and "GEMINI_API_KEY" in resp.json()["detail"]


def test_committed_hosted_index_matches_its_chunks() -> None:
    """Fails if the chunks change without re-running `make hosted-index`."""
    s = Settings(profile="hosted", _env_file=None)
    if not (s.processed_dir / "chunks_article.jsonl").exists():
        pytest.skip("hosted index not built yet")
    chunks = load_chunks(s, "article")
    index = NumpyDenseIndex(s.index_dir, collection_name("article", s.gemini_embedding_model))
    assert index.is_current(fingerprint(chunks, s.gemini_embedding_model))
    assert index.vectors.shape == (len(chunks), s.gemini_embedding_dim)
