"""Retrieval metrics at the level of *legal articles*.

A chunk is relevant if it contains a gold article. Both language versions of
an article count as the same article, and a fixed-size window that spans
several articles gets credit for each of them, so article chunking and fixed
chunking are scored on the same scale.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np

ArticleKey = tuple[str, int]  # (law_id, article number)


def first_hit_ranks(retrieved: Sequence[set[ArticleKey]], gold: set[ArticleKey]) -> dict:
    """Rank (1-based) at which each gold article first appears."""
    found: dict[ArticleKey, int] = {}
    for rank, articles in enumerate(retrieved, start=1):
        for g in gold & articles:
            found.setdefault(g, rank)
    return found


def recall_at_k(retrieved: Sequence[set[ArticleKey]], gold: set[ArticleKey], k: int) -> float:
    found = first_hit_ranks(retrieved[:k], gold)
    return len(found) / len(gold) if gold else 0.0


def reciprocal_rank(retrieved: Sequence[set[ArticleKey]], gold: set[ArticleKey]) -> float:
    found = first_hit_ranks(retrieved, gold)
    return 1.0 / min(found.values()) if found else 0.0


def ndcg_at_k(retrieved: Sequence[set[ArticleKey]], gold: set[ArticleKey], k: int) -> float:
    """Binary nDCG where a gold article only earns gain the first time it shows up.

    Without the "first time" rule, returning the Arabic and English copy of the
    same article would count twice and could push nDCG above the ideal.
    """
    if not gold:
        return 0.0
    seen: set[ArticleKey] = set()
    dcg = 0.0
    for rank, articles in enumerate(retrieved[:k], start=1):
        new = (gold & articles) - seen
        if new:
            dcg += len(new) / math.log2(rank + 1)
            seen |= new
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(gold), k) + 1))
    return min(1.0, dcg / idcg)


def retrieval_metrics(
    retrieved: Sequence[set[ArticleKey]], gold: set[ArticleKey], ks: Iterable[int] = (1, 3, 5, 10)
) -> dict[str, float]:
    out = {f"recall@{k}": recall_at_k(retrieved, gold, k) for k in ks}
    out["mrr"] = reciprocal_rank(retrieved, gold)
    out["ndcg@10"] = ndcg_at_k(retrieved, gold, 10)
    return out


def mean_dict(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}


def latency_summary(values_ms: list[float]) -> dict[str, float]:
    if not values_ms:
        return {}
    arr = np.asarray(values_ms)
    return {
        "mean_ms": float(arr.mean()),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
    }
