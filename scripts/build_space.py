"""Assemble a ready-to-upload Hugging Face Space in deploy/hf_space/build/.

The Space ships the package source, the pre-built article index and the
calibrated threshold, so it starts without re-parsing PDFs or re-embedding.

Usage:  make ingest && make calibrate && make space
Upload: uv run --with huggingface_hub \
          hf upload <user>/marjaa deploy/hf_space/build . --repo-type space
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "deploy" / "hf_space" / "build"
# ZeroGPU supports torch 2.8 - 2.13 (see HF docs, "spaces-zerogpu"); the local
# lock may be newer, so torch is pinned separately for the Space.
ZEROGPU_TORCH = "2.13.0"
PACKAGES = [
    "sentence-transformers",
    "transformers",
    "qdrant-client",
    "rank-bm25",
    "pydantic",
    "pydantic-settings",
    "httpx",
    "numpy",
    "pypdf",
    "beautifulsoup4",
]

SPACE_README = """---
title: Marjaa مرجع
emoji: ⚖️
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: {gradio}
python_version: "3.12"
app_file: app.py
license: mit
short_description: Cited Arabic/English answers on the UAE Labour Law
models:
  - BAAI/bge-m3
  - BAAI/bge-reranker-v2-m3
---

# Marjaa (مرجع)

Ask about the UAE Federal Labour Law (Federal Decree-Law No. 33 of 2021) in Arabic or
English. Answers cite the exact article. Retrieval: BGE-M3 + BM25 hybrid with a BGE
cross-encoder reranker. Generation: Gemini free tier.

Portfolio project, **not legal advice**. The Arabic text is the legally authoritative version.
"""


def locked_versions() -> dict[str, str]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    return {p["name"]: p["version"] for p in lock["package"]}


def main() -> None:
    required = [
        ROOT / "data" / "processed" / "chunks_article.jsonl",
        ROOT / "data" / "index" / "qdrant",
        ROOT / "evals" / "results" / "threshold.json",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"Missing {missing}. Run `make ingest` and `make calibrate` first.")

    if BUILD.exists():
        shutil.rmtree(BUILD)
    (BUILD / "src").mkdir(parents=True)
    shutil.copytree(
        ROOT / "src" / "marjaa",
        BUILD / "src" / "marjaa",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copy(ROOT / "deploy" / "hf_space" / "app.py", BUILD / "app.py")
    for path in [*required, ROOT / "data" / "raw" / "laws.toml"]:
        dest = BUILD / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, dest, ignore=shutil.ignore_patterns("*.lock", ".lock"))
        else:
            shutil.copy(path, dest)

    versions = locked_versions()
    reqs = [f"torch=={ZEROGPU_TORCH}", "spaces"] + [f"{p}=={versions[p]}" for p in PACKAGES]
    (BUILD / "requirements.txt").write_text("\n".join(reqs) + "\n")
    (BUILD / "README.md").write_text(SPACE_README.format(gradio=versions["gradio"]), "utf-8")
    size = sum(f.stat().st_size for f in BUILD.rglob("*") if f.is_file()) / 1e6
    print(f"Space assembled in {BUILD.relative_to(ROOT)} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
