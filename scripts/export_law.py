"""Write web/src/data/law.json: the Labour Law article by article, for the web Library.

    uv run python scripts/export_law.py

Reads the article chunks committed for the hosted demo
(src/marjaa/hosted/chunks_article.jsonl), joins the parts of long articles,
and drops the "Article (N)" / title lines each part repeats. The text is
otherwise unchanged; the web app lays it out (web/src/lib/lawText.ts).
tests/test_web_data.py checks that the file stays in sync with the chunks.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "src" / "marjaa" / "hosted" / "chunks_article.jsonl"
OUT = ROOT / "web" / "src" / "data" / "law.json"

HEADING = re.compile(r"^\s*(?:Article|المادة)\s*\(\s*\d+\s*\)\s*$")


def strip_heading(text: str, title: str) -> str:
    lines = text.split("\n")
    if lines and HEADING.match(lines[0]):
        lines = lines[1:]
        if title and lines and lines[0].strip() == title.strip():
            lines = lines[1:]
    return "\n".join(lines).strip("\n")


def build(chunks: list[dict]) -> dict:
    first = chunks[0]
    parts: dict[tuple[str, int | None], list[dict]] = defaultdict(list)
    for c in chunks:
        parts[(c["language"], c["article"])].append(c)

    def version(lang: str, article: int | None) -> dict | None:
        group = sorted(parts.get((lang, article), []), key=lambda c: c["part"])
        if not group:
            return None
        title = next((c["title"] for c in group if c["title"]), "")
        text = "\n".join(strip_heading(c["text"], c["title"]) for c in group)
        return {
            "title": title,
            "text": text,
            "pages": [group[0]["page_start"], group[-1]["page_end"]],
            "chunks": [c["id"] for c in group],
        }

    numbers = sorted({c["article"] for c in chunks if c["article"] is not None})
    return {
        "law": {
            "id": first["law_id"],
            "name_en": first["law_name_en"],
            "name_ar": first["law_name_ar"],
            "number": first["law_number"],
            "year": first["law_year"],
        },
        "preamble": {"ar": version("ar", None), "en": version("en", None)},
        "articles": [{"n": n, "ar": version("ar", n), "en": version("en", n)} for n in numbers],
    }


def main() -> None:
    chunks = [
        json.loads(line) for line in CHUNKS.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    data = build(chunks)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['articles'])} articles")


if __name__ == "__main__":
    main()
