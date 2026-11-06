"""Discover law files in `data/raw/` and attach metadata from `laws.toml`."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from marjaa.logging_utils import get_logger
from marjaa.schemas import Language, LawInfo

log = get_logger(__name__)

SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm"}
_FILENAME = re.compile(r"^(?P<law_id>.+?)[_-](?P<lang>ar|en)$", re.IGNORECASE)


def load_manifest(raw_dir: Path) -> list[LawInfo]:
    path = raw_dir / "laws.toml"
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [LawInfo(**entry) for entry in data.get("law", [])]


def discover_sources(raw_dir: Path) -> list[tuple[LawInfo, Language, Path]]:
    """Return (law, language, file) for every ingestible file in `raw_dir`."""
    laws = load_manifest(raw_dir)
    by_file = {fname: (law, lang) for law in laws for lang, fname in law.files.items()}
    sources: list[tuple[LawInfo, Language, Path]] = []
    for path in sorted(raw_dir.iterdir()):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if path.name in by_file:
            law, lang = by_file[path.name]
        else:
            match = _FILENAME.match(path.stem)
            if not match:
                log.warning("skipping file with unknown law", extra={"file": path.name})
                continue
            law_id, lang = match["law_id"].lower(), match["lang"].lower()
            law = next((x for x in laws if x.id == law_id), None) or LawInfo(
                id=law_id,
                name_en=law_id.replace("_", " ").title(),
                name_ar=law_id,
            )
            log.info("no manifest entry, using file name", extra={"file": path.name})
        sources.append((law, lang, path))  # type: ignore[arg-type]
    missing = set(by_file) - {p.name for _, _, p in sources}
    for name in sorted(missing):
        log.warning("file listed in laws.toml is missing", extra={"file": name})
    return sources
