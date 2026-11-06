from __future__ import annotations

from pathlib import Path

import pytest

from marjaa.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings pointing at the synthetic fixture law, with no external models."""
    return Settings(
        raw_dir=FIXTURES / "raw",
        processed_dir=tmp_path / "processed",
        index_dir=tmp_path / "index",
        traces_dir=tmp_path / "traces",
        results_dir=tmp_path / "results",
        testset_path=FIXTURES / "testset_smoke.jsonl",
        embedder="hashing",
        llm_provider="fake",
        judge_provider="fake",
        retrieval_mode="hybrid",
        min_relevance=0.0,
        device="cpu",
        # The toy law is ~700 chars; small windows give the fixed strategy >2 chunks.
        fixed_chunk_chars=300,
        fixed_chunk_overlap=60,
        _env_file=None,
    )
