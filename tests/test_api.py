import json

import pytest
from fastapi.testclient import TestClient

from marjaa.api.app import create_app, pipeline_dep
from marjaa.config import Settings
from marjaa.generation.answer import RagPipeline
from marjaa.generation.providers import FakeProvider
from marjaa.ingest.pipeline import run_ingest
from marjaa.retrieval.retriever import build_retriever


@pytest.fixture
def client(settings: Settings) -> TestClient:
    run_ingest(settings)
    pipeline = RagPipeline(build_retriever(settings), FakeProvider(), settings)
    app = create_app(with_ui=False, preload=False)
    app.dependency_overrides[pipeline_dep] = lambda: pipeline
    return TestClient(app)


def _events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["chunks"] > 0
    assert body["llm"] == "fake:extractive"


def test_ask_streams_sources_tokens_done(client: TestClient) -> None:
    resp = client.post("/ask", json={"question": "How long is sick leave?"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _events(resp.text)
    kinds = [e for e, _ in events]
    assert kinds[0] == "sources" and kinds[-1] == "done" and "token" in kinds
    done = events[-1][1]
    assert done["citations"] and all(c["valid"] for c in done["citations"])


def test_ask_non_streaming_and_validation(client: TestClient) -> None:
    resp = client.post("/ask?stream=false", json={"question": "ما مدة الإجازة السنوية؟"})
    data = resp.json()
    assert data["language"] == "ar" and data["sources"]
    assert client.post("/ask", json={"question": ""}).status_code == 422


def test_sources_endpoint(client: TestClient) -> None:
    resp = client.post("/ask?stream=false", json={"question": "maternity leave"})
    source_id = resp.json()["sources"][0]["id"]
    chunk = client.get(f"/sources/{source_id}").json()
    assert chunk["id"] == source_id and chunk["text"]
    assert client.get("/sources/does-not-exist").status_code == 404
