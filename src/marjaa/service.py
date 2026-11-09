"""Builds the shared, long-lived RAG pipeline used by the API, UI and evals."""

from __future__ import annotations

import json
from functools import lru_cache

from marjaa.config import Settings, get_settings
from marjaa.generation.answer import RagPipeline
from marjaa.generation.providers import get_provider
from marjaa.ingest.pipeline import chunks_path, run_ingest
from marjaa.logging_utils import get_logger
from marjaa.retrieval.retriever import build_retriever

log = get_logger(__name__)

DEFAULT_MIN_RELEVANCE = 0.2


def effective_settings(settings: Settings) -> Settings:
    """Fill in the "not found" threshold calibrated by `make calibrate`."""
    if settings.min_relevance is not None:
        return settings
    path = settings.threshold_file
    value = DEFAULT_MIN_RELEVANCE
    if path.exists():
        value = float(json.loads(path.read_text())["threshold"])
    else:
        log.warning("no calibrated threshold, using default", extra={"value": value})
    return settings.model_copy(update={"min_relevance": value})


@lru_cache
def get_pipeline() -> RagPipeline:
    settings = effective_settings(get_settings())
    if not chunks_path(settings, settings.chunk_strategy).exists():
        if settings.profile == "hosted":
            # The hosted API only reads the committed index; it never ingests.
            raise ValueError("hosted index missing: run `make hosted-index` and commit it")
        log.info("no chunks found, running ingestion first")
        run_ingest(settings)
    retriever = build_retriever(settings)
    if settings.retrieval_mode == "hybrid_rerank":
        _ = retriever.reranker  # load now so the first request is not slow
    return RagPipeline(retriever, get_provider(settings), settings)
