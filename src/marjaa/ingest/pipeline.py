"""Ingestion: raw files -> parsed pages -> chunks (both strategies) on disk."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from marjaa.config import ChunkStrategy, Settings
from marjaa.ingest.chunking import article_chunks, fixed_chunks
from marjaa.ingest.laws import discover_sources
from marjaa.ingest.parsers import parse_file, text_quality
from marjaa.logging_utils import get_logger
from marjaa.schemas import Chunk, ParsedDocument

log = get_logger(__name__)


def chunks_path(settings: Settings, strategy: ChunkStrategy) -> Path:
    return settings.processed_dir / f"chunks_{strategy}.jsonl"


def parse_all(settings: Settings, parser: str = "pymupdf") -> list[ParsedDocument]:
    docs = []
    for law, lang, path in discover_sources(settings.raw_dir):
        pages, used = parse_file(path, lang, parser)
        docs.append(
            ParsedDocument(law=law, language=lang, source_file=path.name, parser=used, pages=pages)
        )
        log.info("parsed", extra={"file": path.name, "pages": len(pages), "parser": used})
    if not docs:
        raise FileNotFoundError(
            f"No law files found in {settings.raw_dir}. See README > 'Get the data'."
        )
    return docs


def build_chunks(settings: Settings, docs: list[ParsedDocument]) -> dict[str, list[Chunk]]:
    out: dict[str, list[Chunk]] = {"article": [], "fixed": []}
    for doc in docs:
        out["article"] += article_chunks(doc, settings.max_article_chars)
        out["fixed"] += fixed_chunks(doc, settings.fixed_chunk_chars, settings.fixed_chunk_overlap)
    return out


def write_jsonl(path: Path, rows: list[Chunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(row.model_dump_json() + "\n")


def load_chunks(settings: Settings, strategy: ChunkStrategy) -> list[Chunk]:
    path = chunks_path(settings, strategy)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `make ingest` first.")
    with path.open(encoding="utf-8") as f:
        return [Chunk.model_validate_json(line) for line in f if line.strip()]


def run_ingest(settings: Settings, parser: str = "pymupdf") -> dict[str, int]:
    docs = parse_all(settings, parser)
    chunks = build_chunks(settings, docs)
    for strategy, rows in chunks.items():
        write_jsonl(chunks_path(settings, strategy), rows)  # type: ignore[arg-type]

    # A small report makes ingestion problems visible (missing articles, etc.).
    report = {
        "documents": [
            {
                "file": d.source_file,
                "language": d.language,
                "parser": d.parser,
                "pages": len(d.pages),
                "articles_found": len(
                    {
                        c.article
                        for c in chunks["article"]
                        if c.source_file == d.source_file and c.article is not None
                    }
                ),
                "quality": vars(text_quality("\n".join(p.text for p in d.pages)))
                if d.language == "ar"
                else None,
            }
            for d in docs
        ],
        "chunks": {k: len(v) for k, v in chunks.items()},
        "chunks_by_language": {k: dict(Counter(c.language for c in v)) for k, v in chunks.items()},
    }
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    (settings.processed_dir / "ingest_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("ingest done", extra=report["chunks"])
    return report["chunks"]
