"""End-to-end eval smoke test: the CI gate. No model downloads, no network."""

from marjaa.config import Settings
from marjaa.evaluation.dataset import load_testset
from marjaa.evaluation.experiments import (
    MODES,
    calibrate_threshold,
    evaluate_answers,
    evaluate_retrieval,
)
from marjaa.generation.answer import RagPipeline
from marjaa.generation.providers import FakeProvider
from marjaa.ingest.pipeline import run_ingest
from marjaa.retrieval.retriever import build_retriever


def test_retrieval_eval_smoke(settings: Settings) -> None:
    run_ingest(settings)
    items = load_testset(settings.testset_path)
    for strategy in ("article", "fixed"):
        retriever = build_retriever(settings, strategy)
        for mode in MODES:
            res = evaluate_retrieval(retriever, items, mode)
            assert res["n"] == 7
            assert set(res["overall"]) >= {"recall@5", "mrr", "ndcg@10"}
            # Same-language questions are easy on the toy law for every mode.
            assert res["by_type"]["en"]["recall@5"] == 1.0, (strategy, mode)


def test_answer_eval_and_calibration_smoke(settings: Settings) -> None:
    run_ingest(settings)
    items = load_testset(settings.testset_path)
    retriever = build_retriever(settings)
    cal = calibrate_threshold(retriever, items)
    assert 0.0 <= cal["threshold"] <= 1.0
    s = settings.model_copy(update={"min_relevance": cal["threshold"]})
    pipeline = RagPipeline(retriever, FakeProvider(), s)
    out = evaluate_answers(pipeline, FakeProvider(), items)
    summary = out["summary"]
    assert summary["n_answerable"] == 7 and summary["n_unanswerable"] == 2
    assert summary["citation_validity"] == 1.0  # extractive fake always cites its source
    assert len(out["rows"]) == len(items)


def test_rejudge_keeps_original_grades(settings: Settings) -> None:
    import json

    from evals.runners.rejudge import rejudge_file

    from marjaa.evaluation.experiments import write_json

    run_ingest(settings)
    items = load_testset(settings.testset_path)
    pipeline = RagPipeline(build_retriever(settings), FakeProvider(), settings)
    out = evaluate_answers(pipeline, FakeProvider(), items)
    meta = {
        "date": "x",
        "split": "all",
        "generator": "fake",
        "judge": "old:judge",
        "retrieval": "x",
        "min_relevance": 0.0,
    }
    write_json(settings.results_dir / "run.json", {"meta": meta, **out})

    rejudge_file(settings, "run")
    rejudge_file(settings, "run")  # running twice must not overwrite the original grades
    data = json.loads((settings.results_dir / "run.json").read_text())
    judged = [r for r in data["rows"] if "previous_judge" in r]
    assert judged and all(r["previous_judge"]["judge"] == "old:judge" for r in judged)
    assert data["meta"]["judge"] == "fake:extractive"
    assert data["meta"]["original_judge"] == "old:judge"


def test_answer_eval_resumes_from_checkpoint(settings: Settings, tmp_path) -> None:
    import pytest

    class Boom(FakeProvider):
        def stream(self, system: str, prompt: str):
            raise AssertionError("finished rows must not be recomputed")

    run_ingest(settings)
    items = load_testset(settings.testset_path)
    retriever = build_retriever(settings)
    ckpt, meta = tmp_path / "run.partial.jsonl", {"judge": "fake"}

    first = evaluate_answers(
        RagPipeline(retriever, FakeProvider(), settings), FakeProvider(), items[:4], ckpt, meta
    )
    # A "restart" over the same 4 items must reuse every saved row.
    again = evaluate_answers(
        RagPipeline(retriever, Boom(), settings), Boom(), items[:4], ckpt, meta
    )
    assert [r["id"] for r in again["rows"]] == [r["id"] for r in first["rows"]]
    # Different settings must not silently mix with an old checkpoint.
    with pytest.raises(SystemExit):
        evaluate_answers(
            RagPipeline(retriever, FakeProvider(), settings),
            FakeProvider(),
            items[:4],
            ckpt,
            {"judge": "other"},
        )


def test_parse_judge_recovers_labels_from_broken_json() -> None:
    from marjaa.evaluation.experiments import JUDGE_PARSE_ERROR, parse_judge

    ok = parse_judge('{"faithfulness": 1, "correctness": 0, "reason": "fine"}')
    assert ok == {"faithfulness": 1.0, "correctness": 0.0, "reason": "fine"}
    # An unescaped quote inside the reason breaks json.loads; the labels are still read.
    broken = parse_judge(
        '{\n"faithfulness": 1,\n"correctness": 0,\n"reason": "says "7 days" wrongly"}'
    )
    assert (broken["faithfulness"], broken["correctness"]) == (1.0, 0.0)
    assert parse_judge("no json here")["reason"] == JUDGE_PARSE_ERROR
