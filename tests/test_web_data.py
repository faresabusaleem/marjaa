"""The web Library's copy of the law (web/src/data/law.json) matches the hosted chunks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _export_module():
    spec = importlib.util.spec_from_file_location("export_law", ROOT / "scripts" / "export_law.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_law_json_is_in_sync_with_the_hosted_chunks() -> None:
    export = _export_module()
    chunks = [
        json.loads(line)
        for line in export.CHUNKS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    committed = json.loads(export.OUT.read_text(encoding="utf-8"))
    assert committed == export.build(chunks), "run `uv run python scripts/export_law.py`"


def test_every_article_has_both_languages_and_every_chunk_is_used() -> None:
    export = _export_module()
    data = json.loads(export.OUT.read_text(encoding="utf-8"))
    numbers = [a["n"] for a in data["articles"]]
    assert numbers == list(range(1, len(numbers) + 1))
    used = {cid for a in data["articles"] for lang in ("ar", "en") for cid in a[lang]["chunks"]}
    used |= {cid for lang in ("ar", "en") for cid in data["preamble"][lang]["chunks"]}
    ids = {
        json.loads(line)["id"]
        for line in export.CHUNKS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert used == ids


def test_heading_lines_are_removed_but_text_is_kept() -> None:
    export = _export_module()
    assert (
        export.strip_heading("Article (29)\nAnnual leave\n1. The Worker", "Annual leave")
        == "1. The Worker"
    )
    assert export.strip_heading("المادة (60)\n1. يعاقب", "") == "1. يعاقب"
    assert export.strip_heading("Article (60)\nworkers who were", "Penalties") == "workers who were"
