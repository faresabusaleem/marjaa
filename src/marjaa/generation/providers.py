"""LLM providers behind one small interface.

- `OllamaProvider`: local open model (default, $0, private).
- `GeminiProvider`: Google's free-tier hosted API, used by the deployed demo
  where there is no local GPU/Ollama. Retries 429s with exponential backoff.
- `FakeProvider`: deterministic extractive answers for tests and CI.

Plain `httpx` is used instead of vendor SDKs: the two REST calls are short,
easy to mock in tests, and immune to SDK breaking changes.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections.abc import Callable, Iterator
from typing import Protocol

import httpx

from marjaa.config import Settings
from marjaa.logging_utils import get_logger

log = get_logger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMProvider(Protocol):
    name: str
    model: str

    def stream(self, system: str, prompt: str) -> Iterator[str]: ...


def generate(provider: LLMProvider, system: str, prompt: str) -> str:
    return "".join(provider.stream(system, prompt))


class RetryableError(Exception):
    def __init__(self, status: int, retry_after: float | None = None):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.retry_after = retry_after


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Honour the server's hint: `Retry-After` header or Google's `retryDelay`."""
    header = response.headers.get("retry-after")
    if header and header.replace(".", "", 1).isdigit():
        return float(header)
    try:
        body = response.read().decode("utf-8", "ignore")
    except httpx.HTTPError:
        return None
    match = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
    return float(match.group(1)) if match else None


def with_backoff(
    open_stream: Callable[[], Iterator[str]],
    max_retries: int,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[str]:
    """Retry a streaming call on rate limits / transient errors.

    We only retry if no token has been yielded yet; retrying mid-answer would
    duplicate text the user has already seen.
    """
    attempt = 0
    while True:
        started = False
        try:
            for token in open_stream():
                started = True
                yield token
            return
        except (RetryableError, httpx.TransportError) as exc:
            if started or attempt >= max_retries:
                raise
            hint = exc.retry_after if isinstance(exc, RetryableError) else None
            delay = min(max_delay, hint or base_delay * 2**attempt) + random.uniform(0, 0.5)
            log.warning(
                "API call failed, retrying",
                extra={"error": str(exc), "attempt": attempt + 1, "delay_s": round(delay, 1)},
            )
            sleep(delay)
            attempt += 1


def raise_for_status(response: httpx.Response) -> None:
    if response.status_code in RETRYABLE_STATUS:
        raise RetryableError(response.status_code, _retry_after_seconds(response))
    if response.status_code >= 400:
        body = response.read().decode("utf-8", "ignore")[:500]
        raise RuntimeError(f"LLM request failed: HTTP {response.status_code}: {body}")


class OllamaProvider:
    name = "ollama"

    def __init__(
        self, settings: Settings, client: httpx.Client | None = None, model: str | None = None
    ):
        self.model = model or settings.ollama_model
        self.url = settings.ollama_url.rstrip("/") + "/api/chat"
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.request_timeout_s)

    def _open(self, system: str, prompt: str) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
            # Hidden "thinking" tokens make a small model several times slower
            # and add little for extractive, citation-heavy answers.
            "think": False,
            "options": {
                "temperature": self.settings.temperature,
                "num_predict": self.settings.max_output_tokens,
                "num_ctx": 8192,
            },
        }
        with self.client.stream("POST", self.url, json=payload) as response:
            raise_for_status(response)
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if "error" in data:
                    raise RuntimeError(f"Ollama error: {data['error']}")
                if text := data.get("message", {}).get("content"):
                    yield text

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        return with_backoff(lambda: self._open(system, prompt), self.settings.max_retries)


class GeminiProvider:
    """Gemini via the Interactions REST API (current at the time of writing)."""

    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/interactions?alt=sse"
    API_REVISION = "2026-05-20"

    def __init__(
        self, settings: Settings, client: httpx.Client | None = None, model: str | None = None
    ):
        if settings.gemini_api_key is None:
            raise ValueError("GEMINI_API_KEY is not set (put it in .env)")
        self.model = model or settings.gemini_model
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.request_timeout_s)

    def _open(self, system: str, prompt: str) -> Iterator[str]:
        assert self.settings.gemini_api_key is not None
        headers = {
            "x-goog-api-key": self.settings.gemini_api_key.get_secret_value(),
            "Api-Revision": self.API_REVISION,
        }
        config: dict[str, object] = {"max_output_tokens": self.settings.max_output_tokens}
        if self.settings.gemini_thinking_level:
            config["thinking_level"] = self.settings.gemini_thinking_level
        payload = {
            "model": self.model,
            "system_instruction": system,
            "input": prompt,
            "stream": True,
            "generation_config": config,
        }
        with self.client.stream("POST", self.URL, json=payload, headers=headers) as response:
            raise_for_status(response)
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                yield from _gemini_text(json.loads(data))

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        return with_backoff(lambda: self._open(system, prompt), self.settings.max_retries)


def _gemini_text(event: dict) -> Iterator[str]:
    if "error" in event:
        err = event["error"]
        status = err.get("code") if isinstance(err, dict) else None
        if status in RETRYABLE_STATUS:
            raise RetryableError(int(status))
        raise RuntimeError(f"Gemini error: {err}")
    # Interactions API: {"event_type": "step.delta", "delta": {"type": "text", "text": ...}}
    if event.get("event_type") == "step.delta":
        delta = event.get("delta") or {}
        if delta.get("type") == "text" and delta.get("text"):
            yield delta["text"]
        return
    # Older generateContent-style chunks, kept as a fallback.
    for cand in event.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if part.get("text") and not part.get("thought"):
                yield part["text"]


class FakeProvider:
    """Offline stand-in: answers with the first sentence of the first source.

    Lets the whole pipeline (API, UI, eval runners) run in CI with zero
    network calls, while still producing parseable citations.
    """

    name = "fake"
    model = "extractive"

    def stream(self, system: str, prompt: str) -> Iterator[str]:
        if "JUDGE" in system:
            yield json.dumps({"faithfulness": 1, "correctness": 1, "reason": "fake judge"})
            return
        if "standalone" in system:  # follow-up rewriting: return the question unchanged
            match = re.search(r"Follow-up question: (.+)", prompt)
            yield match.group(1).strip() if match else prompt
            return
        match = re.search(r'<source[^>]*citation="([^"]+)"[^>]*>\s*(.+?)</source>', prompt, re.S)
        if not match:
            yield "Not found in the provided laws."
            return
        citation, text = match.groups()
        body = " ".join(text.split())
        sentence = re.split(r"(?<=[.!?؟])\s", body)[0][:300]
        for word in f"{sentence} {citation}".split(" "):
            yield word + " "


def get_provider(
    settings: Settings, name: str | None = None, model: str | None = None
) -> LLMProvider:
    """`model` overrides the provider's default model (used for the judge)."""
    name = name or settings.llm_provider
    if name == "ollama":
        return OllamaProvider(settings, model=model)
    if name == "gemini":
        return GeminiProvider(settings, model=model)
    if name == "fake":
        return FakeProvider()
    raise ValueError(f"unknown provider {name!r}")
