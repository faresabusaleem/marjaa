"""Sparse (BM25) and dense (Qdrant local mode) indexes, plus RRF fusion."""

from __future__ import annotations

import atexit
import hashlib
import json
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from marjaa.ingest.normalize import tokenize
from marjaa.logging_utils import get_logger
from marjaa.schemas import Chunk

log = get_logger(__name__)

Hits = list[tuple[str, float]]  # (chunk_id, score), best first


class BM25Index:
    """Okapi BM25 over normalised, light-stemmed tokens.

    Keyword search catches exact legal terms and article numbers that dense
    embeddings can blur; it cannot match across languages.
    """

    def __init__(self, chunks: list[Chunk]):
        self.ids = [c.id for c in chunks]
        self.languages = np.array([c.language for c in chunks])
        self.bm25 = BM25Okapi([tokenize(c.search_text) or ["_"] for c in chunks])

    def search(self, query: str, limit: int, language: str | None = None) -> Hits:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = np.asarray(self.bm25.get_scores(tokens))
        if language:
            scores = np.where(self.languages == language, scores, -np.inf)
        order = np.argsort(-scores)[:limit]
        return [(self.ids[i], float(scores[i])) for i in order if scores[i] > 0]


_QDRANT_CLIENTS: dict[str, object] = {}


def _qdrant(path: Path | None):
    """Qdrant local mode locks its folder, so share one client per path."""
    from qdrant_client import QdrantClient

    key = str(path) if path else ":memory:"
    if key not in _QDRANT_CLIENTS:
        if path:
            path.mkdir(parents=True, exist_ok=True)
            client = QdrantClient(path=str(path))
        else:
            client = QdrantClient(":memory:")
        atexit.register(client.close)  # release the folder lock cleanly on exit
        _QDRANT_CLIENTS[key] = client
    return _QDRANT_CLIENTS[key]


def fingerprint(chunks: list[Chunk], model: str) -> str:
    h = hashlib.sha256(model.encode())
    for c in chunks:
        h.update(c.id.encode())
        h.update(c.text.encode())
    return h.hexdigest()[:16]


def embedding_text(chunk: Chunk) -> str:
    header = f"{chunk.law_name} | {chunk.chapter}" if chunk.chapter else chunk.law_name
    return f"{header}\n{chunk.text}"


class DenseIndex:
    """Cosine search over chunk embeddings stored in Qdrant (embedded, no server)."""

    def __init__(self, path: Path | None, collection: str):
        self.client = _qdrant(path)
        self.path = path
        self.collection = collection

    def _meta_path(self) -> Path | None:
        return self.path / f"{self.collection}.json" if self.path else None

    def is_current(self, fp: str) -> bool:
        meta = self._meta_path()
        if not meta or not meta.exists() or not self.client.collection_exists(self.collection):
            return False
        return json.loads(meta.read_text()).get("fingerprint") == fp

    def build(self, chunks: list[Chunk], vectors: np.ndarray, fp: str) -> None:
        from qdrant_client import models

        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            self.collection,
            vectors_config=models.VectorParams(
                size=int(vectors.shape[1]), distance=models.Distance.COSINE
            ),
        )
        self.client.upload_points(
            self.collection,
            points=[
                models.PointStruct(
                    id=i,
                    vector=vectors[i].tolist(),
                    payload={"chunk_id": c.id, "language": c.language, "law_id": c.law_id},
                )
                for i, c in enumerate(chunks)
            ],
        )
        if meta := self._meta_path():
            meta.write_text(json.dumps({"fingerprint": fp, "count": len(chunks)}))
        log.info("dense index built", extra={"collection": self.collection, "n": len(chunks)})

    def search(self, vector: np.ndarray, limit: int, language: str | None = None) -> Hits:
        from qdrant_client import models

        flt = None
        if language:
            flt = models.Filter(
                must=[
                    models.FieldCondition(key="language", match=models.MatchValue(value=language))
                ]
            )
        result = self.client.query_points(
            self.collection, query=vector.tolist(), limit=limit, query_filter=flt
        )
        return [(p.payload["chunk_id"], float(p.score)) for p in result.points]


def reciprocal_rank_fusion(rankings: list[Hits], k: int = 60) -> Hits:
    """RRF: score(d) = sum over lists of 1 / (k + rank).

    Uses only ranks, so BM25 scores (unbounded) and cosine similarities
    (0..1) can be combined without any score calibration.
    """
    fused: dict[str, float] = {}
    for hits in rankings:
        for rank, (cid, _) in enumerate(hits, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
