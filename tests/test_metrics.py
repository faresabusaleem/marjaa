import pytest

from marjaa.evaluation.metrics import ndcg_at_k, recall_at_k, reciprocal_rank, retrieval_metrics

A1, A2, A3 = ("law", 1), ("law", 2), ("law", 3)


def test_recall_and_mrr() -> None:
    retrieved = [{A3}, {A1}, {A2}]
    assert recall_at_k(retrieved, {A1}, 1) == 0.0
    assert recall_at_k(retrieved, {A1}, 2) == 1.0
    assert recall_at_k(retrieved, {A1, A2}, 2) == 0.5
    assert reciprocal_rank(retrieved, {A1}) == 0.5
    assert reciprocal_rank(retrieved, {("law", 9)}) == 0.0


def test_ndcg_perfect_and_duplicates_do_not_double_count() -> None:
    assert ndcg_at_k([{A1}, {A2}], {A1, A2}, 10) == pytest.approx(1.0)
    # Arabic + English copy of the same article: second copy earns nothing.
    dup = ndcg_at_k([{A1}, {A1}, {A2}], {A1, A2}, 10)
    assert dup < 1.0


def test_fixed_window_covering_two_gold_articles_is_perfect() -> None:
    assert ndcg_at_k([{A1, A2}], {A1, A2}, 10) == pytest.approx(1.0)
    assert recall_at_k([{A1, A2}], {A1, A2}, 1) == 1.0


def test_retrieval_metrics_keys() -> None:
    m = retrieval_metrics([{A1}], {A1})
    assert m == {
        "recall@1": 1.0,
        "recall@3": 1.0,
        "recall@5": 1.0,
        "recall@10": 1.0,
        "mrr": 1.0,
        "ndcg@10": 1.0,
    }
