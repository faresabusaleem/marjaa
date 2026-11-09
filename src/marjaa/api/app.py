"""FastAPI service: /ask (Server-Sent Events stream), /health, /sources/{id}.

The same routes are also served under /api, the prefix the Next.js web app
uses (on Vercel the /api/* paths are routed to this app, see vercel.json).
Locally the Gradio UI can be mounted at /ui in the same process, so both share
one loaded copy of the models and the index.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from marjaa.generation.answer import AnswerResult, RagPipeline, Turn
from marjaa.generation.providers import RetryableError
from marjaa.logging_utils import get_logger, setup_logging
from marjaa.schemas import Chunk
from marjaa.service import get_pipeline

log = get_logger("marjaa.api")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000, examples=["كم مدة الإجازة السنوية؟"])
    # Earlier turns, oldest first, so a follow-up like "and for part-time
    # workers?" can be rewritten into a standalone question.
    history: list[Turn] = Field(default_factory=list, max_length=6)


def pipeline_dep() -> RagPipeline:
    try:
        return get_pipeline()
    except ValueError as exc:  # e.g. GEMINI_API_KEY missing on the server
        raise HTTPException(status_code=503, detail=str(exc)) from exc


Pipeline = Annotated[RagPipeline, Depends(pipeline_dep)]


def _sse(events: Iterator[dict]) -> Iterator[str]:
    try:
        for event in events:
            payload = json.dumps(event["data"], ensure_ascii=False)
            yield f"event: {event['event']}\ndata: {payload}\n\n"
    except Exception as exc:  # headers are sent: report the failure in-band
        busy = isinstance(exc, RetryableError) and exc.status == 429
        log.exception("ask stream failed")
        data = {"code": "busy" if busy else "error", "message": str(exc)[:200]}
        yield f"event: error\ndata: {json.dumps(data)}\n\n"


router = APIRouter()


@router.get("/health")
def health(pipeline: Pipeline) -> dict:
    s = pipeline.settings
    return {
        "status": "ok",
        "profile": s.profile,
        "chunks": len(pipeline.retriever.chunks),
        "chunk_strategy": s.chunk_strategy,
        "retrieval_mode": s.retrieval_mode,
        "embedder": s.embedder_label,
        "llm": f"{pipeline.provider.name}:{pipeline.provider.model}",
        "min_relevance": s.min_relevance,
    }


@router.post("/ask", response_model=None)
def ask(
    req: AskRequest,
    pipeline: Pipeline,
    stream: Annotated[bool, Query(description="Stream tokens as SSE")] = True,
) -> StreamingResponse | AnswerResult:
    """Streams events: `sources` (retrieved articles), many `token`s, then
    `done` (full answer, validated citations, latency, trace id).
    Use `?stream=false` for a single JSON response."""
    if not stream:
        return pipeline.answer(req.question, req.history)
    return StreamingResponse(
        _sse(pipeline.stream(req.question, req.history)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sources/{chunk_id}")
def source(chunk_id: str, pipeline: Pipeline) -> Chunk:
    chunk = pipeline.retriever.get(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail=f"unknown source {chunk_id!r}")
    return chunk


def create_app(with_ui: bool = False, preload: bool = True, api_only: bool = False) -> FastAPI:
    """`api_only`: serve the routes under /api only (the hosted deployment)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging()
        if preload:
            get_pipeline()  # load models at startup, not on the first request
        yield

    docs = "/api/docs" if api_only else "/docs"
    app = FastAPI(
        title="Marjaa API",
        description="Bilingual Arabic/English question answering over UAE law, with citations.",
        version="0.2.0",
        lifespan=lifespan,
        docs_url=docs,
        openapi_url=f"{docs.removesuffix('/docs')}/openapi.json",
        redoc_url=None,
    )
    if api_only:
        app.include_router(router, prefix="/api")
    else:
        app.include_router(router)
        app.include_router(router, prefix="/api", include_in_schema=False)

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
