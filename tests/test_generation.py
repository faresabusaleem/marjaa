import json

import httpx
import pytest
from pydantic import SecretStr

from marjaa.config import Settings
from marjaa.generation.answer import RagPipeline, select_context
from marjaa.generation.citations import citation_coverage, extract_citations, is_not_found
from marjaa.generation.providers import (
    FakeProvider,
    GeminiProvider,
    OllamaProvider,
    RetryableError,
    generate,
    with_backoff,
)
from marjaa.ingest.pipeline import load_chunks, run_ingest
from marjaa.retrieval.retriever import build_retriever
from marjaa.schemas import Chunk, RetrievedChunk


def _chunk(article: int, lang: str = "en", part: int = 0) -> Chunk:
    return Chunk(
        id=f"law-{lang}-a{article}-p{part}",
        law_id="labour",
        law_name="Federal Labour Law" if lang == "en" else "قانون العمل الاتحادي",
        law_name_en="Federal Labour Law",
        law_name_ar="قانون العمل الاتحادي",
        language=lang,
        strategy="article",
        article=article,
        articles=[article],
        part=part,
        text=f"Article ({article}) text",
        search_text="",
        source_file="x.pdf",
        page_start=1,
        page_end=1,
    )


SOURCES = [_chunk(30), _chunk(31, "ar")]


def test_citations_are_parsed_and_validated() -> None:
    answer = (
        "Leave is 30 days [Federal Labour Law, Article 30]. "
        "Also [Federal Labour Law, Article 99]. "
        "وكذلك [قانون العمل الاتحادي، المادة (٣١)]."
    )
    cites = extract_citations(answer, SOURCES)
    assert [(c.article, c.valid) for c in cites] == [(30, True), (99, False), (31, True)]
    assert cites[0].chunk_id == "law-en-a30-p0"


def test_multi_article_citation_and_unknown_law() -> None:
    cites = extract_citations("[Federal Labour Law, Articles 30 and 31]", SOURCES)
    assert [c.article for c in cites] == [30, 31] and all(c.valid for c in cites)
    unknown = extract_citations("[Traffic Law, Article 30]", SOURCES)
    assert unknown[0].law_id is None and not unknown[0].valid


def test_citation_coverage_and_not_found() -> None:
    text = (
        "The worker gets thirty days of leave [Federal Labour Law, Article 30]. "
        "Another long uncited sentence here."
    )
    assert citation_coverage(text) == 0.5
    assert is_not_found("Not found in the provided laws.")
    assert is_not_found("لم يتم العثور على إجابة في القوانين المتاحة.")
    assert not is_not_found("Leave is 30 days [Federal Labour Law, Article 30].")


def test_select_context_dedupes_languages_preferring_question_language() -> None:
    ranked = [
        RetrievedChunk(chunk=c, score=1.0)
        for c in (_chunk(30, "en"), _chunk(30, "ar"), _chunk(31, "en"))
    ]
    ctx = select_context(ranked, "ar", 5)
    assert [(r.chunk.article, r.chunk.language) for r in ctx] == [(30, "ar"), (31, "en")]


def test_backoff_retries_before_first_token_only() -> None:
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RetryableError(429, retry_after=1.0)
        yield "ok"

    out = list(with_backoff(flaky, max_retries=5, sleep=sleeps.append))
    assert out == ["ok"] and attempts["n"] == 3 and len(sleeps) == 2
    assert all(1.0 <= s <= 1.5 for s in sleeps)  # honours retry_after (+ jitter)

    def gives_up():
        raise RetryableError(429)
        yield  # pragma: no cover

    with pytest.raises(RetryableError):
        list(with_backoff(gives_up, max_retries=2, sleep=lambda _: None))


def test_ollama_provider_streams_ndjson(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["think"] is False and body["stream"] is True
        lines = [
            {"message": {"content": "Hello "}},
            {"message": {"content": "world"}},
            {"done": True},
        ]
        return httpx.Response(200, text="\n".join(json.dumps(x) for x in lines))

    provider = OllamaProvider(settings, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert generate(provider, "sys", "hi") == "Hello world"


def test_gemini_provider_parses_sse_and_retries_429(settings: Settings, monkeypatch) -> None:
    monkeypatch.setattr("marjaa.generation.providers.time.sleep", lambda _: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.headers["x-goog-api-key"] == "test-key"
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": {"details": [{"retryDelay": "0s"}]}})
        events = [
            {"event_type": "step.start"},
            {"event_type": "step.delta", "delta": {"type": "thought", "text": "hidden"}},
            {"event_type": "step.delta", "delta": {"type": "text", "text": "مرحبا"}},
            {"event_type": "step.delta", "delta": {"type": "text", "text": " بك"}},
        ]
        sse = "".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events)
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    s = settings.model_copy(update={"gemini_api_key": SecretStr("test-key")})
    provider = GeminiProvider(s, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert generate(provider, "sys", "hi") == "مرحبا بك"
    assert calls["n"] == 2


def test_pipeline_end_to_end_with_fake_llm(settings: Settings) -> None:
    run_ingest(settings)
    pipeline = RagPipeline(build_retriever(settings), FakeProvider(), settings)
    events = list(pipeline.stream("How long is maternity leave?"))
    assert events[0]["event"] == "sources"
    assert events[-1]["event"] == "done"
    result = pipeline.answer("How long is maternity leave?")
    assert not result.abstained
    assert result.citations and result.all_citations_valid
    assert result.citations[0].article == 5
    assert list(settings.traces_dir.rglob("*.json"))  # trace saved


def test_pipeline_abstains_on_low_relevance(settings: Settings) -> None:
    run_ingest(settings)
    strict = settings.model_copy(update={"min_relevance": 0.99, "retrieval_mode": "hybrid_rerank"})
    pipeline = RagPipeline(build_retriever(strict), FakeProvider(), strict)
    result = pipeline.answer("What is the speed limit on highways?")
    assert result.abstained and result.abstain_reason == "low_relevance"
    assert result.answer == "Not found in the provided laws."


def test_arabic_question_gets_arabic_citations(settings: Settings) -> None:
    run_ingest(settings)
    assert load_chunks(settings, "article")
    pipeline = RagPipeline(build_retriever(settings), FakeProvider(), settings)
    result = pipeline.answer("ما مدة إجازة الوضع؟")
    assert result.language == "ar"
    assert result.sources[0].citation.startswith("[قانون الإجازات النموذجي، المادة")
