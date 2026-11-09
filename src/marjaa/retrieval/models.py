"""Embedding and reranking models behind small interfaces.

Real models (BGE-M3, BGE reranker v2-m3) are used locally. The hosted demo
embeds with the Gemini API instead (`GeminiEmbedder`), which needs no weights.
Tiny deterministic stand-ins (`HashingEmbedder`, `OverlapReranker`) let unit
tests and CI run in seconds without downloading ~4.5 GB of weights.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

import httpx
import numpy as np

from marjaa.generation.providers import raise_for_status, with_backoff
from marjaa.ingest.normalize import normalize_for_search, tokenize
from marjaa.logging_utils import get_logger

if TYPE_CHECKING:
    from marjaa.config import Settings

log = get_logger(__name__)


class Embedder(Protocol):
    name: str
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:
        """Embed documents (chunks)."""
        ...

    def encode_query(self, text: str) -> np.ndarray:
        """Embed one search query (some models embed queries differently)."""
        ...


class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...


def pick_device(preferred: str | None = None) -> str:
    if preferred:
        return preferred
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class SentenceTransformerEmbedder:
    """BGE-M3 dense embeddings (1024-d, multilingual incl. Arabic, 8k context).

    BGE-M3 maps Arabic and English into one space, which is what makes
    cross-lingual retrieval (Arabic question -> English article) work.
    It needs no query instruction prefix.
    """

    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        max_seq_length: int = 1024,
        revision: str | None = None,
    ):
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self.device = pick_device(device)
        self.model = SentenceTransformer(model_name, device=self.device, revision=revision)
        # Articles are short; capping length keeps memory and latency low.
        self.model.max_seq_length = max_seq_length
        self.dim = int(self.model.get_embedding_dimension() or 1024)
        log.info("embedder loaded", extra={"model": model_name, "device": self.device})

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts, batch_size=8, normalize_embeddings=True, convert_to_numpy=True
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        return self.encode([text])[0]  # BGE-M3 needs no query instruction


class CrossEncoderReranker:
    """BGE reranker v2-m3: reads (query, passage) together, outputs relevance.

    Sigmoid-normalised scores in [0, 1] double as a confidence signal for the
    "not found in the provided laws" decision.
    """

    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        max_length: int = 1024,
        fp16: bool = False,
    ):
        import torch
        from sentence_transformers import CrossEncoder

        self.device = pick_device(device)
        # fp16 only helps on accelerators; on CPU it is slower or unsupported.
        dtype = torch.float16 if fp16 and self.device != "cpu" else torch.float32
        self.model = CrossEncoder(
            model_name,
            device=self.device,
            max_length=max_length,
            activation_fn=torch.nn.Sigmoid(),
            model_kwargs={"torch_dtype": dtype},
        )
        log.info(
            "reranker loaded",
            extra={
                "model": model_name,
                "device": self.device,
                "dtype": str(dtype),
                "max_length": max_length,
            },
        )

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        scores = self.model.predict([(query, p) for p in passages], batch_size=8)
        return [float(s) for s in np.asarray(scores).reshape(-1)]


class HashingEmbedder:
    """Character n-gram feature hashing. Deterministic, no model download."""

    def __init__(self, dim: int = 512):
        self.name = "hashing"
        self.dim = dim

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        norm = normalize_for_search(text)
        for word in norm.split():
            padded = f" {word} "
            for n in (3, 4):
                for i in range(len(padded) - n + 1):
                    h = int(hashlib.md5(padded[i : i + n].encode()).hexdigest()[:8], 16)
                    vec[h % self.dim] += 1.0
        length = float(np.linalg.norm(vec))
        return vec / length if length else vec

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vector(t) for t in texts]) if texts else np.zeros((0, self.dim))

    def encode_query(self, text: str) -> np.ndarray:
        return self._vector(text)


def query_prompt(text: str) -> str:
    return f"task: search result | query: {text}"


def document_prompt(text: str) -> str:
    # Chunks are embedded as "header\ntext" (see indexes.embedding_text); the
    # header (law + article title) becomes the document title.
    title, _, body = text.partition("\n")
    return f"title: {title or 'none'} | text: {body or title}"


class GeminiEmbedder:
    """Gemini embeddings through the free API, for the hosted demo.

    gemini-embedding-2 has no `task_type` parameter; Google's docs instead mark
    retrieval queries and documents with the prompt prefixes used below. It is
    multilingual, so Arabic and English share one vector space, as with BGE-M3.
    """

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
    BATCH = 50

    def __init__(
        self,
        model: str,
        dim: int,
        api_key: str,
        max_retries: int = 5,
        timeout_s: float = 60.0,
        client: httpx.Client | None = None,
    ):
        self.name = model
        self.dim = dim
        self.api_key = api_key
        self.max_retries = max_retries
        self.client = client or httpx.Client(timeout=timeout_s)
        # Evals search the same question in several modes; embed it once.
        self._queries: dict[str, np.ndarray] = {}

    def _post(self, texts: list[str]) -> list[list[float]]:
        body = {
            "requests": [
                {
                    "model": f"models/{self.name}",
                    "content": {"parts": [{"text": t}]},
                    "output_dimensionality": self.dim,
                }
                for t in texts
            ]
        }
        response = self.client.post(
            self.URL.format(model=self.name), json=body, headers={"x-goog-api-key": self.api_key}
        )
        raise_for_status(response)
        return [e["values"] for e in response.json()["embeddings"]]

    def _embed(self, texts: list[str]) -> np.ndarray:
        rows: list[list[float]] = []
        for i in range(0, len(texts), self.BATCH):
            batch = texts[i : i + self.BATCH]

            def call(batch: list[str] = batch):
                yield self._post(batch)

            rows.extend(next(with_backoff(call, self.max_retries)))
        vectors = np.asarray(rows, dtype=np.float32).reshape(len(rows), -1)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1, norms)

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return self._embed([document_prompt(t) for t in texts])

    def encode_query(self, text: str) -> np.ndarray:
        if text not in self._queries:
            self._queries[text] = self._embed([query_prompt(text)])[0]
        return self._queries[text]

    def clear_cache(self) -> None:
        """Forget cached queries, so a latency measurement includes the API call."""
        self._queries.clear()


class OverlapReranker:
    """Share of query tokens found in the passage. Test stand-in for a cross-encoder."""

    def score(self, query: str, passages: list[str]) -> list[float]:
        q = set(tokenize(query))
        return [len(q & set(tokenize(p))) / max(1, len(q)) for p in passages]


@lru_cache(maxsize=4)
def load_embedder(
    name: str, model_name: str, device: str | None, revision: str | None = None
) -> Embedder:
    if name == "hashing":
        return HashingEmbedder()
    return SentenceTransformerEmbedder(model_name, device, revision=revision)


@lru_cache(maxsize=4)
def _gemini_embedder(model: str, dim: int, api_key: str, max_retries: int) -> GeminiEmbedder:
    return GeminiEmbedder(model, dim, api_key, max_retries)


def embedder_for(settings: Settings) -> Embedder:
    if settings.embedder == "gemini":
        if settings.gemini_api_key is None:
            raise ValueError("GEMINI_API_KEY is not set (put it in .env)")
        return _gemini_embedder(
            settings.gemini_embedding_model,
            settings.gemini_embedding_dim,
            settings.gemini_api_key.get_secret_value(),
            settings.max_retries,
        )
    return load_embedder(
        settings.embedder, settings.embedding_model, settings.device, settings.embedding_revision
    )


@lru_cache(maxsize=4)
def load_reranker(
    name: str, model_name: str, device: str | None, max_length: int = 1024, fp16: bool = False
) -> Reranker:
    if name == "hashing":  # test mode pairs the hashing embedder with the overlap reranker
        return OverlapReranker()
    return CrossEncoderReranker(model_name, device, max_length, fp16)
