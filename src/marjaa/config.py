"""Central configuration, read from environment variables and `.env`.

Every setting can be overridden with an env var prefixed `MARJAA_`, e.g.
`MARJAA_LLM_PROVIDER=gemini`. Secrets (API keys) only ever live in `.env`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]

ChunkStrategy = Literal["article", "fixed"]
RetrievalMode = Literal["dense", "bm25", "hybrid", "hybrid_rerank"]
ProviderName = Literal["ollama", "gemini", "fake"]
EmbedderName = Literal["bge-m3", "hashing"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MARJAA_", env_file=ROOT_DIR / ".env", extra="ignore"
    )

    # --- Paths -----------------------------------------------------------------
    raw_dir: Path = ROOT_DIR / "data" / "raw"
    processed_dir: Path = ROOT_DIR / "data" / "processed"
    index_dir: Path = ROOT_DIR / "data" / "index"
    traces_dir: Path = ROOT_DIR / "data" / "traces"
    results_dir: Path = ROOT_DIR / "evals" / "results"
    testset_path: Path = ROOT_DIR / "evals" / "datasets" / "testset.jsonl"

    # --- Chunking --------------------------------------------------------------
    chunk_strategy: ChunkStrategy = "article"
    # Articles longer than this (in characters) are sub-split so a chunk stays
    # within the embedder's sweet spot and the LLM prompt stays small.
    max_article_chars: int = 2500
    fixed_chunk_chars: int = 1200
    fixed_chunk_overlap: int = 200

    # --- Retrieval -------------------------------------------------------------
    embedder: EmbedderName = "bge-m3"
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    device: str | None = None  # None = auto (cuda > mps > cpu)
    retrieval_mode: RetrievalMode = "hybrid_rerank"
    candidates_per_retriever: int = 30  # depth of each list before fusion
    rerank_candidates: int = 20  # how many fused results the cross-encoder sees
    rrf_k: int = 60  # standard RRF constant from Cormack et al. (2009)
    top_k: int = 5  # chunks passed to the LLM

    # Reranker sigmoid score below which we answer "not found". Calibrated on
    # the dev split by `make calibrate`; see evals/results/threshold.json.
    min_relevance: float = 0.2

    # --- Generation ------------------------------------------------------------
    llm_provider: ProviderName = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    temperature: float = 0.1
    max_output_tokens: int = 700
    request_timeout_s: float = 180.0
    max_retries: int = 5

    # --- Evaluation ------------------------------------------------------------
    judge_provider: ProviderName = "ollama"

    # --- Service ---------------------------------------------------------------
    log_level: str = "INFO"
    save_traces: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
