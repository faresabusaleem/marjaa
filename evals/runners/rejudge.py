"""Re-grade stored answers with the current judge, without regenerating them.

Used for the prompt ablation: the earlier runs' answers came from older
prompts, so they can't be regenerated with today's code, but they can be graded
again by today's judge so every column of the comparison uses the same judge.

Progress is saved after every answer, and already re-graded answers are
skipped, so an interrupted run can simply be started again.

The judge is shown exactly the articles the generator saw: taken from the
row's `context_ids`, or else from the saved query trace (matched on question +
answer). The previous grades are kept in each row under `previous_judge`, which
also gives a judge-agreement measurement on identical answers.

Usage: uv run python -m evals.runners.rejudge answers_rules_only_prompt answers_study_leave_example
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from evals.runners.run_answers import to_markdown
from marjaa.config import Settings, get_settings
from marjaa.evaluation.dataset import load_testset
from marjaa.evaluation.experiments import judge_answer, summarise_answers, write_json
from marjaa.generation.answer import to_source
from marjaa.generation.providers import get_provider
from marjaa.ingest.pipeline import load_chunks
from marjaa.logging_utils import get_logger, setup_logging
from marjaa.schemas import RetrievedChunk

log = get_logger("eval.rejudge")


def trace_context(traces_dir: Path) -> dict[tuple[str, str], list[str]]:
    """(question, answer) -> context chunk ids, from saved per-query traces."""
    out: dict[tuple[str, str], list[str]] = {}
    for path in traces_dir.rglob("*.json"):
        trace = json.loads(path.read_text(encoding="utf-8"))
        ids = trace.get("retrieval", {}).get("context_ids")
        if ids:
            out[(trace["question"], trace["answer"])] = ids
    return out


def rejudge_file(settings: Settings, name: str) -> dict:
    path = settings.results_dir / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    items = {i.id: i for i in load_testset(settings.testset_path)}
    chunks = {c.id: c for c in load_chunks(settings, settings.chunk_strategy)}
    traces = trace_context(settings.traces_dir)
    judge = get_provider(settings, settings.judge_provider, model=settings.judge_model)
    judge_label = f"{judge.name}:{judge.model}"
    old_judge = data["meta"].get("original_judge", data["meta"]["judge"])

    for row in data["rows"]:
        if not row["answerable"] or row["abstained"]:
            continue
        if row.get("judged_by") == judge_label:
            continue  # already re-graded by this judge (resuming an interrupted run)
        ids = row.get("context_ids") or traces.get((row["question"], row["answer"]))
        if not ids:
            raise SystemExit(f"{name}/{row['id']}: no stored context; cannot re-judge exactly")
        item = items[row["id"]]
        sources = [
            to_source(RetrievedChunk(chunk=chunks[cid], score=0.0), item.question_lang)
            for cid in ids
        ]
        # Keep the ORIGINAL grades once; re-running this script must not overwrite them.
        row.setdefault(
            "previous_judge",
            {
                "judge": old_judge,
                "correctness": row.get("correctness"),
                "faithfulness": row.get("faithfulness"),
            },
        )
        row["context_ids"] = ids
        row.update(judge_answer(judge, item, row["answer"], sources))
        row["judged_by"] = judge_label
        write_json(path, data)  # save after every answer so an interruption loses little
        log.info("rejudged", extra={"file": name, "id": row["id"]})

    data["summary"] = summarise_answers(data["rows"])
    data["meta"]["original_judge"] = old_judge
    data["meta"]["judge"] = judge_label
    data["meta"]["rejudged"] = datetime.now(UTC).strftime("%Y-%m-%d")
    write_json(path, data)
    (settings.results_dir / f"{name}.md").write_text(
        to_markdown(data["summary"], data["meta"]), encoding="utf-8"
    )
    return data["summary"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="+", help="result files in evals/results (no .json)")
    args = parser.parse_args()
    setup_logging()
    settings = get_settings()
    for name in args.names:
        summary = rejudge_file(settings, name)
        print(name, {k: summary[k] for k in ("correctness", "faithfulness")})


if __name__ == "__main__":
    main()
