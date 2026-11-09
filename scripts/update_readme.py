"""Copy the generated result tables into README.md between marker comments,
and write the numbers the web app's "How it works" page shows.

Every number in the README and on the site comes from evals/results/, which
the eval runners write. Run after `make eval` (the Makefile does this for you).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"
WEB_DATA = ROOT / "web" / "src" / "data" / "results.json"
HOSTED_THRESHOLD = ROOT / "src" / "marjaa" / "hosted" / "threshold.json"


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


def kappa(a: list[float], b: list[float]) -> float:
    """Cohen's kappa for two binary raters: agreement corrected for chance."""
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def _judge_pairs(judges: set[tuple[str, str]] | None = None):
    """Old vs new judge grades on the same stored answers (evals/runners/rejudge.py)."""
    pairs: dict[str, tuple[list[float], list[float]]] = {
        "correctness": ([], []),
        "faithfulness": ([], []),
    }
    for name, _ in RUNS[:-1]:
        data = _load(name)
        for row in (data or {}).get("rows", []):
            prev = row.get("previous_judge")
            if not prev:
                continue
            if judges is not None:
                judges.add((prev["judge"], data["meta"]["judge"]))
            for key, (old, new) in pairs.items():
                if prev.get(key) is not None and row.get(key) is not None:
                    old.append(prev[key])
                    new.append(row[key])
    return pairs


def judge_agreement() -> str:
    """Old vs new judge on the same stored answers (from evals/runners/rejudge.py)."""
    judges: set[tuple[str, str]] = set()
    pairs = _judge_pairs(judges)
    if not pairs["correctness"][0]:
        return "Not measured.\n"
    old_j, new_j = sorted(judges)[0]
    rows = [
        f"The same {len(pairs['correctness'][0])} answers graded by `{old_j}` and `{new_j}`:",
        "",
        "| Label | Agreement | Cohen's kappa | Rate, old judge | Rate, new judge |",
        "|---|---|---|---|---|",
    ]
    for key, (old, new) in pairs.items():
        agree = sum(x == y for x, y in zip(old, new, strict=True)) / len(old)
        rows.append(
            f"| {key} | {pct(agree)} | {kappa(old, new):.2f} | {pct(sum(old) / len(old))} "
            f"| {pct(sum(new) / len(new))} |"
        )
    return "\n".join(rows) + "\n"


def block(name: str) -> str:
    if name == "prompt_comparison":
        return prompt_comparison()
    if name == "judge_agreement":
        return judge_agreement()
    if name == "threshold":
        data = json.loads((RESULTS / "threshold.json").read_text())
        return (
            f"Calibrated on the dev split ({data['n_answerable']} answerable, "
            f"{data['n_unanswerable']} unanswerable questions): threshold "
            f"**{data['threshold']}** on the reranker's top score, balanced accuracy "
            f"{data['balanced_accuracy']:.3f}.\n"
        )
    return (RESULTS / f"{name}.md").read_text(encoding="utf-8")


def _load(name: str) -> dict | None:
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _retrieval(data: dict | None, strategy: str = "article") -> dict | None:
    if not data:
        return None
    out: dict = {"meta": data["meta"], "modes": {}}
    for r in data["results"]:
        if r["strategy"] != strategy:
            continue
        single = [row["recall@1"] for row in r["rows"] if row["type"] != "multi"]
        out["modes"][r["mode"]] = {
            "recall@1": r["overall"]["recall@1"],
            "recall@5": r["overall"]["recall@5"],
            "mrr": r["overall"]["mrr"],
            "single_recall@1": sum(single) / len(single) if single else None,
            "by_type_recall@5": {t: v["recall@5"] for t, v in r["by_type"].items()},
            "p50_ms": r["latency"]["p50_ms"],
        }
    return out


def _answers(data: dict | None) -> dict | None:
    if not data:
        return None
    s = data["summary"]
    keys = [k for k in s if k != "latency"]
    return {
        "meta": data["meta"],
        **{k: s[k] for k in keys},
        "p50_total_ms": s["latency"]["total"]["p50_ms"],
        "p50_first_token_ms": (s["latency"]["first_token"] or {}).get("p50_ms"),
    }


def web_results() -> dict:
    """Only measured numbers; a missing run is null and the page says so."""
    testset = [
        json.loads(line)
        for line in (ROOT / "evals" / "datasets" / "testset.jsonl").read_text().splitlines()
        if line.strip()
    ]
    types: dict[str, int] = {}
    for row in testset:
        types[row["type"]] = types.get(row["type"], 0) + 1
    agreement = None
    pairs = _judge_pairs()
    if pairs["correctness"][0]:
        old, new = pairs["correctness"]
        agreement = {
            "n": len(old),
            "agreement": sum(x == y for x, y in zip(old, new, strict=True)) / len(old),
            "kappa": kappa(old, new),
        }
    hosted_threshold = (
        json.loads(HOSTED_THRESHOLD.read_text()) if HOSTED_THRESHOLD.exists() else None
    )
    return {
        "testset": {"n": len(testset), "types": types},
        "retrieval": {
            "local": _retrieval(_load("retrieval")),
            "local_fixed": _retrieval(_load("retrieval"), "fixed"),
            "hosted": _retrieval(_load("retrieval_hosted")),
        },
        "answers": {
            "local": _answers(_load("answers")),
            "hosted": _answers(_load("answers_hosted")),
        },
        "prompt_ablation": [
            {
                "label": label,
                **{k: (_load(name) or {}).get("summary", {}).get(k) for k, _ in COMPARE},
            }
            for name, label in RUNS
        ],
        "judge_agreement": agreement,
        "threshold": {
            "local": {k: v for k, v in (_load("threshold") or {}).items() if "scores" not in k},
            "hosted": {k: v for k, v in (hosted_threshold or {}).items() if "scores" not in k}
            or None,
        },
    }


def main() -> None:
    WEB_DATA.parent.mkdir(parents=True, exist_ok=True)
    WEB_DATA.write_text(json.dumps(web_results(), indent=2) + "\n", encoding="utf-8")
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    for name in (
        "retrieval",
        "retrieval_fast_rerank",
        "answers",
        "prompt_comparison",
        "judge_agreement",
        "threshold",
    ):
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
