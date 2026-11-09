"""Central configuration, read from environment variables and `.env`.

Every setting can be overridden with an env var prefixed `MARJAA_`, e.g.
`MARJAA_LLM_PROVIDER=gemini`. Secrets (API keys) only ever live in `.env`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
# Ships inside the package so the hosted API finds it wherever it is installed.
HOSTED_DIR = Path(__file__).resolve().parent / "hosted"

ChunkStrategy = Literal["article", "fixed"]
RetrievalMode = Literal["dense", "bm25", "hybrid", "hybrid_rerank"]
ProviderName = Literal["ollama", "gemini", "fake"]
EmbedderName = Literal["bge-m3", "hashing", "gemini"]
DenseBackend = Literal["qdrant", "numpy"]
Profile = Literal["local", "hosted"]

# The hosted demo runs on Vercel functions: no GPU and a 500 MB bundle cap, so
# BGE-M3 and the cross-encoder (4.5 GB with PyTorch) cannot come along. It uses
# Gemini embeddings with vectors precomputed into HOSTED_DIR, an in-memory
# index, BM25 + RRF without a reranker, and Gemini for answers. Explicitly set
# variables still win over these defaults.
HOSTED_DEFAULTS: dict[str, object] = {
    "embedder": "gemini",
    "dense_backend": "numpy",
    "retrieval_mode": "hybrid",
    "llm_provider": "gemini",
    "chunk_strategy": "article",
    "processed_dir": HOSTED_DIR,
    "index_dir": HOSTED_DIR,
    "threshold_path": HOSTED_DIR / "threshold.json",
    "save_traces": False,  # the function's filesystem is read-only
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MARJAA_", env_file=ROOT_DIR / ".env", extra="ignore", populate_by_name=True
    )

    # local: BGE-M3 + reranker + Ollama. hosted: see HOSTED_DEFAULTS.
    profile: Profile = "local"

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
    dense_backend: DenseBackend = "qdrant"
    embedding_model: str = "BAAI/bge-m3"
    gemini_embedding_model: str = "gemini-embedding-2"
    # 768 of the 3072 dimensions: Google's recommended smaller size, 4x less to ship.
    gemini_embedding_dim: int = 768
    # Pinned to the commit that adds model.safetensors (Hub PR #130). BGE-M3's
    # main branch only ships pytorch_model.bin, so an unpinned load downloads
    # BOTH formats (2 x 2.3 GB); pinning keeps one safetensors copy and makes
    # the embedding model reproducible. Set to "main" to follow upstream.
    embedding_revision: str | None = "9a0624b896d81da7492a910ffa53731274b6cf3d"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    device: str | None = None  # None = auto (cuda > mps > cpu)
    retrieval_mode: RetrievalMode = "hybrid_rerank"
    candidates_per_retriever: int = 30  # depth of each list before fusion
    rerank_candidates: int = 20  # how many fused results the cross-encoder sees
    rerank_max_length: int = 1024  # tokens per (question, article) pair
    rerank_fp16: bool = False  # half precision on GPU/MPS: faster, tiny score drift
    rrf_k: int = 60  # standard RRF constant from Cormack et al. (2009)
    top_k: int = 5  # chunks passed to the LLM

    # Top retrieval score (reranker probability, or dense cosine without a
    # reranker) below which we answer "not found". None = use the value
    # calibrated on the dev split by `make calibrate`, read from threshold_file.
    min_relevance: float | None = None
    threshold_path: Path | None = None  # None = results_dir / threshold.json

    # --- Generation ------------------------------------------------------------
    llm_provider: ProviderName = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    # Lowest thinking level keeps latency and free-tier token use down.
    # Valid levels differ per model (flash-lite: minimal|low|medium|high).
    gemini_thinking_level: str | None = "minimal"
    temperature: float = 0.1
    max_output_tokens: int = 700
    request_timeout_s: float = 180.0
    max_retries: int = 5

    # --- Evaluation ------------------------------------------------------------
    judge_provider: ProviderName = "ollama"
    # A different, larger model than the generator, so the judge is not grading
    # its own answers. For judge_provider=gemini set e.g. gemini-3.8-flash.
    judge_model: str | None = "qwen3.5:9b"

    # --- Service ---------------------------------------------------------------
    log_level: str = "INFO"
    save_traces: bool = True

    @model_validator(mode="after")
    def _apply_profile(self) -> Settings:
        if self.profile == "hosted":
            for key, value in HOSTED_DEFAULTS.items():
                if key not in self.model_fields_set:
                    setattr(self, key, value)
        return self

    @property
    def threshold_file(self) -> Path:
        return self.threshold_path or self.results_dir / "threshold.json"

    @property
    def embedder_label(self) -> str:
        if self.embedder == "gemini":
            return self.gemini_embedding_model
        return self.embedding_model if self.embedder == "bge-m3" else self.embedder


@lru_cache
def get_settings() -> Settings:
    return Settings()
