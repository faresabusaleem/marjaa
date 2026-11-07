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


COMPARE = [
    ("correctness", "Correctness (judge)"),
    ("faithfulness", "Faithfulness (judge)"),
    ("citation_validity", "Citation validity"),
    ("answers_with_citation", "Answers with at least one citation"),
    ("gold_article_cited", "Gold article cited"),
    ("citation_coverage", "Sentences carrying a citation"),
]


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


RUNS = [
    ("answers_rules_only_prompt", "Rules only"),
    ("answers_study_leave_example", "+ example (study leave)"),
    ("answers", "+ example (parks, final)"),
]


def prompt_comparison() -> str:
    runs = [
        (label, json.loads((RESULTS / f"{name}.json").read_text())["summary"])
        for name, label in RUNS
        if (RESULTS / f"{name}.json").exists()
    ]
    rows = ["| Metric | " + " | ".join(label for label, _ in runs) + " |"]
    rows.append("|---|" + "---|" * len(runs))
    rows += [
        f"| {label} | " + " | ".join(pct(s.get(k)) for _, s in runs) + " |" for k, label in COMPARE
    ]
    return "\n".join(rows) + "\n"


def block(name: str) -> str:
    if name == "prompt_comparison":
        return prompt_comparison()
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
    for name in ("retrieval", "retrieval_fast_rerank", "answers", "prompt_comparison", "threshold"):
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
