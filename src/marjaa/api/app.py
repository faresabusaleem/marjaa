"""FastAPI service: /ask (Server-Sent Events stream), /health, /sources/{id}.

The Gradio UI is mounted at /ui in the same process so both share one loaded
copy of the models and the index.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from marjaa.generation.answer import AnswerResult, RagPipeline
from marjaa.logging_utils import setup_logging
from marjaa.schemas import Chunk
from marjaa.service import get_pipeline


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000, examples=["كم مدة الإجازة السنوية؟"])


def pipeline_dep() -> RagPipeline:
    return get_pipeline()


Pipeline = Annotated[RagPipeline, Depends(pipeline_dep)]


def _sse(events: Iterator[dict]) -> Iterator[str]:
    for event in events:
        payload = json.dumps(event["data"], ensure_ascii=False)
        yield f"event: {event['event']}\ndata: {payload}\n\n"


def create_app(with_ui: bool = False, preload: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging()
        if preload:
            get_pipeline()  # load models at startup, not on the first request
        yield

    app = FastAPI(
        title="Marjaa API",
        description="Bilingual Arabic/English question answering over UAE law, with citations.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health(pipeline: Pipeline) -> dict:
        s = pipeline.settings
        return {
            "status": "ok",
            "chunks": len(pipeline.retriever.chunks),
            "chunk_strategy": s.chunk_strategy,
            "retrieval_mode": s.retrieval_mode,
            "llm": f"{pipeline.provider.name}:{pipeline.provider.model}",
            "min_relevance": s.min_relevance,
        }

    @app.post("/ask", response_model=None)
    def ask(
        req: AskRequest,
        pipeline: Pipeline,
        stream: Annotated[bool, Query(description="Stream tokens as SSE")] = True,
    ) -> StreamingResponse | AnswerResult:
        """Streams events: `sources` (retrieved articles), many `token`s, then
        `done` (full answer, validated citations, latency, trace id).
        Use `?stream=false` for a single JSON response."""
        if not stream:
            return pipeline.answer(req.question)
        return StreamingResponse(
            _sse(pipeline.stream(req.question)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/sources/{chunk_id}")
    def source(chunk_id: str, pipeline: Pipeline) -> Chunk:
        chunk = pipeline.retriever.get(chunk_id)
        if chunk is None:
            raise HTTPException(status_code=404, detail=f"unknown source {chunk_id!r}")
        return chunk

    if with_ui:
        import gradio as gr

        from marjaa.ui.app import UI_CSS, UI_HEAD, build_ui, theme

        app = gr.mount_gradio_app(
            app, build_ui(get_pipeline), path="/ui", css=UI_CSS, head=UI_HEAD, theme=theme()
        )

        @app.get("/", include_in_schema=False)
        def root() -> RedirectResponse:
            return RedirectResponse("/ui")

    return app
