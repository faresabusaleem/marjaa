"""Copy the generated result tables into README.md between marker comments.

Every number in the README comes from evals/results/*.md, which the eval
runners write. Run after `make eval` (the Makefile does this for you).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"


def block(name: str) -> str:
    if name == "threshold":
        data = json.loads((RESULTS / "threshold.json").read_text())
        return (
            f"Calibrated on the dev split ({data['n_answerable']} answerable, "
            f"{data['n_unanswerable']} unanswerable questions): threshold "
            f"**{data['threshold']}** on the reranker's top score, balanced accuracy "
            f"{data['balanced_accuracy']:.3f}.\n"
        )
    return (RESULTS / f"{name}.md").read_text(encoding="utf-8")


def main() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    for name in ("retrieval", "answers", "threshold"):
        pattern = re.compile(
            rf"(<!-- results:{name}:start -->\n).*?(<!-- results:{name}:end -->)", re.S
        )
        if not pattern.search(text):
            continue
        text = pattern.sub(lambda m, n=name: m.group(1) + block(n) + m.group(2), text)
    # Parser quality scores from the last ingest.
    report = json.loads((RESULTS / "ingest_report.json").read_text())
    scores = next(d["parser_scores"] for d in report["documents"] if d["language"] == "ar")
    text = re.sub(
        r"(<!-- q:(\w+) -->)[^|\n]*",
        lambda m: f"{m.group(1)} {scores.get(m.group(2), 'n/a')} ",
        text,
    )
    readme.write_text(text, encoding="utf-8")
    print("README results updated")


if __name__ == "__main__":
    main()
