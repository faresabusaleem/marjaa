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
