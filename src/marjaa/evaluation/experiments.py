"""Experiment logic shared by the eval runners and the CI smoke test."""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from marjaa.config import ChunkStrategy, RetrievalMode
from marjaa.evaluation.dataset import EvalItem
from marjaa.evaluation.metrics import ArticleKey, latency_summary, mean_dict, retrieval_metrics
from marjaa.generation.answer import RagPipeline, Source
from marjaa.generation.prompts import example_leaked
from marjaa.generation.providers import LLMProvider, generate
from marjaa.logging_utils import get_logger
from marjaa.retrieval.retriever import Retriever

log = get_logger(__name__)

MODES: list[RetrievalMode] = ["dense", "bm25", "hybrid", "hybrid_rerank"]
STRATEGIES: list[ChunkStrategy] = ["article", "fixed"]


def chunk_articles(retriever: Retriever, chunk_ids: list[str]) -> list[set[ArticleKey]]:
    out = []
    for cid in chunk_ids:
        c = retriever.chunks[cid]
        out.append({(c.law_id, a) for a in c.articles})
    return out


def evaluate_retrieval(
    retriever: Retriever, items: list[EvalItem], mode: RetrievalMode, k: int = 10
) -> dict[str, Any]:
    """Run every answerable question; return per-question rows + aggregates."""
    rows = []
    for item in items:
        if not item.answerable:
            continue
        result = retriever.retrieve(item.question, mode=mode, top_k=k, language=item.search_lang)
        ids = [r.chunk.id for r in result.chunks]
        metrics = retrieval_metrics(chunk_articles(retriever, ids), item.gold_keys)
        rows.append(
            {
                "id": item.id,
                "type": item.type,
                "retrieved": ids,
                "latency_ms": result.latency_ms["total"],
                **metrics,
            }
        )
    by_type: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_type[row["type"]].append(row)
    metric_keys = ["recall@1", "recall@3", "recall@5", "recall@10", "mrr", "ndcg@10"]
    pick = lambda rs: [{m: r[m] for m in metric_keys} for r in rs]  # noqa: E731
    return {
        "mode": mode,
        "n": len(rows),
        "overall": mean_dict(pick(rows)),
        "by_type": {t: {"n": len(rs), **mean_dict(pick(rs))} for t, rs in sorted(by_type.items())},
        "latency": latency_summary([r["latency_ms"] for r in rows]),
        "rows": rows,
    }


def calibrate_threshold(retriever: Retriever, items: list[EvalItem]) -> dict[str, Any]:
    """Pick the top-relevance cut-off (reranker probability, or dense cosine
    without a reranker) that best separates answerable from unanswerable
    questions (max balanced accuracy) on the given items."""
    answerable, unanswerable = [], []
    mode = retriever.settings.retrieval_mode
    for item in items:
        result = retriever.retrieve(item.question, mode=mode, top_k=1)
        score = result.top_relevance or 0.0
        (answerable if item.answerable else unanswerable).append(score)
    candidates = sorted(set(answerable + unanswerable)) or [0.0]
    best = (0.0, 0.0)
    for t in candidates:
        tpr = np.mean([s >= t for s in answerable]) if answerable else 0.0
        tnr = np.mean([s < t for s in unanswerable]) if unanswerable else 0.0
        bal = (tpr + tnr) / 2
        if bal > best[0]:
            best = (float(bal), float(t))
    # Place the cut halfway to the next lower score so it is not on a data point.
    lower = [s for s in candidates if s < best[1]]
    threshold = (best[1] + max(lower)) / 2 if lower else best[1]
    return {
        "threshold": round(threshold, 4),
        "signal": "reranker probability" if mode == "hybrid_rerank" else "dense cosine similarity",
        "balanced_accuracy": round(best[0], 4),
        "n_answerable": len(answerable),
        "n_unanswerable": len(unanswerable),
        "answerable_scores": sorted(round(s, 4) for s in answerable),
        "unanswerable_scores": sorted(round(s, 4) for s in unanswerable),
    }


JUDGE_SYSTEM = """You are a strict JUDGE grading answers from a legal question-answering system about UAE law. Reply with JSON only."""

JUDGE_PROMPT = """Question:
{question}

Reference answer (written from the correct article):
{reference}

Sources the system was given:
{sources}

System answer:
{answer}

Grade the system answer:
- "faithfulness": 1 if every statement in the system answer is supported by the sources, otherwise 0.
- "correctness": 1 if the system answer gives the same key facts as the reference answer (same numbers, durations, conditions); missing extra detail is fine, contradicting or omitting the main fact is not. Otherwise 0.
The answers may be in Arabic or English; judge the meaning, not the language.

Return JSON: {{"faithfulness": 0 or 1, "correctness": 0 or 1, "reason": "one short sentence"}}"""


def judge_answer(
    judge: LLMProvider, item: EvalItem, answer: str, sources: list[Source]
) -> dict[str, Any]:
    context = "\n\n".join(f"{s.citation}\n{s.text[:1500]}" for s in sources)
    prompt = JUDGE_PROMPT.format(
        question=item.question,
        reference=item.reference_answer,
        sources=context,
        answer=answer,
    )
    return parse_judge(generate(judge, JUDGE_SYSTEM, prompt))


JUDGE_PARSE_ERROR = "judge parse error"


def parse_judge(raw: str) -> dict[str, Any]:
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        data = json.loads(raw[start:end])
        return {
            "faithfulness": float(bool(int(data.get("faithfulness", 0)))),
            "correctness": float(bool(int(data.get("correctness", 0)))),
            "reason": str(data.get("reason", ""))[:300],
        }
    except (ValueError, TypeError):
        pass
    # The judge sometimes breaks the JSON inside its free-text "reason" (e.g. an
    # unescaped quote around Arabic text) while the two 0/1 labels are intact.
    labels = {
        k: re.search(rf'"{k}"\s*:\s*"?([01])\b', raw) for k in ("faithfulness", "correctness")
    }
    if all(labels.values()):
        reason = re.search(r'"reason"\s*:\s*"(.*)', raw, re.S)
        return {
            **{k: float(m.group(1)) for k, m in labels.items() if m},
            "reason": reason.group(1).rstrip('"}\n ')[:300] if reason else "",
        }
    log.warning("judge returned invalid JSON", extra={"raw": raw[:200]})
    return {"faithfulness": 0.0, "correctness": 0.0, "reason": JUDGE_PARSE_ERROR}


def load_checkpoint(path: Path, meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Rows already finished by an interrupted run with the same settings."""
    if not path.exists():
        return {}
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if not lines or lines[0].get("_meta") != meta:
        raise SystemExit(
            f"{path.name} was written with different settings; rerun with --fresh to discard it."
        )
    return {row["id"]: row for row in lines[1:]}


def evaluate_answers(
    pipeline: RagPipeline,
    judge: LLMProvider,
    items: list[EvalItem],
    checkpoint: Path | None = None,
    checkpoint_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Answer and grade every item. With `checkpoint`, each finished row is
    appended to a JSONL file as it completes, and a rerun skips finished rows,
    so a crash or shutdown only loses the question in progress."""
    meta = checkpoint_meta or {}
    done = load_checkpoint(checkpoint, meta) if checkpoint else {}
    if done:
        log.info("resuming from checkpoint", extra={"done": len(done), "of": len(items)})
    elif checkpoint:
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(json.dumps({"_meta": meta}) + "\n", encoding="utf-8")
    rows = []
    for i, item in enumerate(items, 1):
        if item.id in done:
            rows.append(done[item.id])
            continue
        t = time.perf_counter()
        result = pipeline.answer(item.question)
        cited = {(c.law_id, c.article) for c in result.citations}
        row: dict[str, Any] = {
            "id": item.id,
            "type": item.type,
            "answerable": item.answerable,
            "question": item.question,
            "answer": result.answer,
            "abstained": result.abstained,
            "abstain_reason": result.abstain_reason,
            "top_relevance": result.top_relevance,
            "n_citations": len(result.citations),
            "n_valid_citations": sum(c.valid for c in result.citations),
            "cited_gold": len(cited & item.gold_keys),
            "n_gold": len(item.gold_keys),
            "citation_coverage": result.citation_coverage,
            "example_leaked": example_leaked(result.answer),
            # Exactly what the model saw, so answers can be re-judged later.
            "trace_id": result.trace_id,
            "context_ids": [s.id for s in result.sources],
            "latency_ms": result.latency_ms,
            "wall_ms": (time.perf_counter() - t) * 1000,
        }
        if item.answerable and not result.abstained:
            row.update(judge_answer(judge, item, result.answer, result.sources))
        rows.append(row)
        if checkpoint:
            with checkpoint.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        log.info(
            "answered eval item",
            extra={"i": i, "of": len(items), "id": item.id, "abstained": result.abstained},
        )
    return {"summary": summarise_answers(rows), "rows": rows}


def _rate(values: list[float]) -> float | None:
    return round(float(np.mean(values)), 4) if values else None


def summarise_answers(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ans = [r for r in rows if r["answerable"]]
    una = [r for r in rows if not r["answerable"]]
    answered = [r for r in ans if not r["abstained"]]
    all_cites = sum(r["n_citations"] for r in rows)
    gen = [r["latency_ms"] for r in rows if "generation" in r["latency_ms"]]
    return {
        "n_answerable": len(ans),
        "n_unanswerable": len(una),
        # Quality of the answers the system chose to give (judged by the LLM).
        "correctness": _rate([r["correctness"] for r in answered if "correctness" in r]),
        "faithfulness": _rate([r["faithfulness"] for r in answered if "faithfulness" in r]),
        # Over all answerable questions, counting abstentions as wrong.
        "correct_over_all_answerable": _rate([r.get("correctness", 0.0) for r in ans]),
        # Citation checks are computed in code, not by the judge.
        "citation_validity": round(sum(r["n_valid_citations"] for r in rows) / all_cites, 4)
        if all_cites
        else None,
        "answers_with_citation": _rate([float(r["n_citations"] > 0) for r in answered]),
        "gold_article_cited": _rate([r["cited_gold"] / r["n_gold"] for r in answered]),
        "citation_coverage": _rate([r["citation_coverage"] for r in answered]),
        # Did text from the prompt's format example leak into an answer?
        "format_example_leaks": sum(bool(r.get("example_leaked")) for r in rows)
        if any("example_leaked" in r for r in rows)
        else None,  # not measured in runs made before the leak check existed
        # "Not found" behaviour.
        "unanswerable_abstention": _rate([float(r["abstained"]) for r in una]),
        "false_abstention": _rate([float(r["abstained"]) for r in ans]),
        "latency": {
            "retrieval": latency_summary([r["latency_ms"]["retrieval"] for r in rows]),
            "first_token": latency_summary([x["first_token"] for x in gen if "first_token" in x]),
            "total": latency_summary([r["latency_ms"]["total"] for r in rows]),
        },
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
