"""Auto-generate the evaluation test set from the law text with a local LLM.

For each sampled article the LLM writes one question + reference answer. The
gold label is the article the question was generated from, so no human
labelling is needed (the trade-off: questions are only as good as the
generator; see README > Limitations).

Question types
- ar / en          question and article in the same language
- cross_ar_en      Arabic question, must be answered from the ENGLISH text
- cross_en_ar      English question, must be answered from the ARABIC text
- multi            needs two related (adjacent, same-chapter) articles
- unanswerable     about UAE topics this law does not cover (expect "not found")

Usage: uv run python -m evals.runners.generate_testset [--seed 42]
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import re
from collections import Counter, defaultdict

import httpx

from marjaa.config import Settings, get_settings
from marjaa.evaluation.dataset import EvalItem, GoldRef, save_testset
from marjaa.ingest.normalize import detect_language
from marjaa.ingest.pipeline import load_chunks
from marjaa.logging_utils import get_logger, setup_logging

log = get_logger("testset")

COUNTS = {"ar": 34, "en": 34, "cross_ar_en": 12, "cross_en_ar": 12, "multi": 12}
# Seeds for out-of-scope questions. Hand-picked topics governed by *other*
# UAE laws (traffic, tax, family, real estate...), phrased by the LLM.
UNANSWERABLE_TOPICS = [
    "the fine for running a red light in Dubai",
    "the minimum share capital required to set up a limited liability company",
    "the VAT rate charged on goods",
    "how an estate is divided between sons and daughters under inheritance rules",
    "the requirements to obtain a UAE driving licence",
    "how long a UAE tourist visa is valid",
    "how much a landlord in Dubai may increase the rent",
    "the minimum legal age for marriage",
    "the punishment for possessing narcotic drugs",
    "how to register a trademark",
    "who gets custody of children after a divorce",
    "the corporate income tax rate on business profits",
    "whether foreigners may buy freehold property",
    "the penalty for online defamation under the cybercrime law",
    "the conditions for obtaining UAE citizenship",
    "the rules for bringing prescription medicines into the country",
    "the penalty for littering in public places",
    "how to obtain a building permit for a villa",
    "the conditions for adopting a child",
    "the maximum interest rate banks may charge on personal loans",
    "the requirements for registering a marriage contract",
    "the punishment for cheque bouncing",
    "how long a car must be insured",
    "the legal blood alcohol limit for drivers",
]
LANG_NAME = {"ar": "Arabic", "en": "English"}
SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string"}, "answer": {"type": "string"}},
    "required": ["question", "answer"],
}

SINGLE_PROMPT = """You write evaluation questions for a question-answering system about UAE law.

Read the legal article below. Write ONE realistic question that an employee or employer might ask, which this article answers clearly and completely. Then write the correct answer using ONLY this article.

Rules:
- Write the question in {q_lang} and the answer in {q_lang}.
- Do NOT mention the article number or say "this article" in the question.
- Make the question specific (include the situation or condition it is about).
- The answer is 1-2 sentences and copies any numbers (days, amounts, percentages) exactly.

Article ({src_lang}):
\"\"\"
{text}
\"\"\"

Return JSON: {{"question": "...", "answer": "..."}}"""

MULTI_PROMPT = """You write evaluation questions for a question-answering system about UAE law.

Read the TWO legal articles below. Write ONE realistic question whose complete answer needs information from BOTH articles (for example, it asks about two related rules at once). Then write the correct answer using ONLY these articles.

Rules:
- Write the question in {q_lang} and the answer in {q_lang}.
- Do NOT mention article numbers in the question.
- The answer is 2-3 sentences and copies numbers exactly.

Article A ({src_lang}):
\"\"\"
{text_a}
\"\"\"

Article B ({src_lang}):
\"\"\"
{text_b}
\"\"\"

Return JSON: {{"question": "...", "answer": "..."}}"""

UNANSWERABLE_PROMPT = """Write ONE short, natural question in {q_lang} that a resident of the UAE might ask about {topic}.
Return JSON: {{"question": "...", "answer": ""}}"""

_ARTICLE_MENTION = re.compile(r"(article|المادة|مادة)\s*\(?\s*[0-9٠-٩]+", re.I)


def ask_json(settings: Settings, prompt: str, seed: int) -> dict:
    """Ollama structured output: the JSON schema constrains decoding."""
    response = httpx.post(
        settings.ollama_url.rstrip("/") + "/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "format": SCHEMA,
            "options": {"temperature": 0.4, "seed": seed, "num_ctx": 8192},
        },
        timeout=settings.request_timeout_s,
    )
    response.raise_for_status()
    return json.loads(response.json()["message"]["content"])


def is_good(item: dict, q_lang: str, answerable: bool) -> bool:
    q, a = item.get("question", "").strip(), item.get("answer", "").strip()
    if not (10 <= len(q) <= 300) or detect_language(q) != q_lang:
        return False
    if _ARTICLE_MENTION.search(q):
        return False  # would leak the gold label
    return not answerable or (5 <= len(a) <= 700 and detect_language(a) == q_lang)


def article_texts(settings: Settings) -> dict[tuple[str, int, str], dict]:
    """(law_id, article, lang) -> {text, chapter}; merges sub-split parts."""
    merged: dict[tuple[str, int, str], dict] = {}
    for c in load_chunks(settings, "article"):
        if c.article is None:
            continue
        key = (c.law_id, c.article, c.language)
        entry = merged.setdefault(key, {"parts": [], "chapter": c.chapter})
        entry["parts"].append(c.text)
    return {k: {"text": "\n".join(v["parts"]), "chapter": v["chapter"]} for k, v in merged.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dev-share", type=float, default=0.3)
    args = parser.parse_args()
    setup_logging()
    settings = get_settings()
    rng = random.Random(args.seed)

    texts = article_texts(settings)
    # Only articles present in both languages with substantive text. Very long
    # articles (definitions) are truncated in the prompt for the small LLM.
    eligible = sorted(
        {(law, art) for (law, art, _) in texts}
        & {
            (law, art)
            for (law, art, lang) in texts
            if lang == "ar" and len(texts[(law, art, lang)]["text"]) >= 250
        }
        & {(law, art) for (law, art, lang) in texts if lang == "en"}
    )
    log.info("eligible articles", extra={"n": len(eligible)})

    items: list[EvalItem] = []
    counter = Counter()

    def add(qtype: str, q: dict, q_lang: str, gold: list[tuple[str, int]], src_lang, search_lang):
        counter[qtype] += 1
        items.append(
            EvalItem(
                id=f"{qtype}-{counter[qtype]:03d}",
                type=qtype,  # type: ignore[arg-type]
                question=q["question"].strip(),
                question_lang=q_lang,  # type: ignore[arg-type]
                search_lang=search_lang,
                gold=[GoldRef(law_id=law, article=a) for law, a in gold],
                reference_answer=q.get("answer", "").strip(),
                source_text_lang=src_lang,
            )
        )

    def generate(prompt: str, q_lang: str, answerable: bool) -> dict | None:
        for attempt in range(3):
            try:
                q = ask_json(settings, prompt, seed=args.seed + attempt + len(items) * 7)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
                log.warning("generation failed", extra={"error": str(exc)})
                continue
            if is_good(q, q_lang, answerable):
                return q
        return None

    # Single-article questions. Each article is used at most once per type.
    plan = [  # (type, question language, source text language, search restriction)
        ("ar", "ar", "ar", None),
        ("en", "en", "en", None),
        ("cross_ar_en", "ar", "en", "en"),
        ("cross_en_ar", "en", "ar", "ar"),
    ]
    for qtype, q_lang, src_lang, search_lang in plan:
        pool = eligible[:]
        rng.shuffle(pool)
        for law, art in pool:
            if counter[qtype] >= COUNTS[qtype]:
                break
            text = texts[(law, art, src_lang)]["text"][:4000]
            prompt = SINGLE_PROMPT.format(
                q_lang=LANG_NAME[q_lang], src_lang=LANG_NAME[src_lang], text=text
            )
            if q := generate(prompt, q_lang, answerable=True):
                add(qtype, q, q_lang, [(law, art)], src_lang, search_lang)
                log.info("item", extra={"type": qtype, "article": art, "q": q["question"][:80]})

    # Multi-article questions: adjacent articles from the same chapter.
    pairs = [
        (a, b)
        for a, b in itertools.pairwise(eligible)
        if a[0] == b[0]
        and b[1] == a[1] + 1
        and texts[(a[0], a[1], "en")]["chapter"] == texts[(b[0], b[1], "en")]["chapter"]
    ]
    rng.shuffle(pairs)
    for i, (a, b) in enumerate(pairs):
        if counter["multi"] >= COUNTS["multi"]:
            break
        lang = "ar" if i % 2 == 0 else "en"
        prompt = MULTI_PROMPT.format(
            q_lang=LANG_NAME[lang],
            src_lang=LANG_NAME[lang],
            text_a=texts[(a[0], a[1], lang)]["text"][:2500],
            text_b=texts[(b[0], b[1], lang)]["text"][:2500],
        )
        if q := generate(prompt, lang, answerable=True):
            add("multi", q, lang, [a, b], lang, None)

    # Unanswerable questions, alternating languages.
    for i, topic in enumerate(UNANSWERABLE_TOPICS):
        lang = "ar" if i % 2 == 0 else "en"
        prompt = UNANSWERABLE_PROMPT.format(q_lang=LANG_NAME[lang], topic=topic)
        if q := generate(prompt, lang, answerable=False):
            add("unanswerable", {"question": q["question"], "answer": ""}, lang, [], None, None)

    # Deduplicate and assign a stratified dev/test split.
    seen, unique = set(), []
    for item in items:
        if item.question not in seen:
            seen.add(item.question)
            unique.append(item)
    by_type: dict[str, list[EvalItem]] = defaultdict(list)
    for item in unique:
        by_type[item.type].append(item)
    for group in by_type.values():
        rng.shuffle(group)
        n_dev = round(len(group) * args.dev_share)
        for j, item in enumerate(group):
            item.split = "dev" if j < n_dev else "test"

    save_testset(settings.testset_path, unique)
    summary = Counter((i.type, i.split) for i in unique)
    log.info("testset saved", extra={"n": len(unique), "path": str(settings.testset_path)})
    print(json.dumps({f"{t}/{s}": n for (t, s), n in sorted(summary.items())}, indent=2))


if __name__ == "__main__":
    main()
