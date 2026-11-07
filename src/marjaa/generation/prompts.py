"""Prompt templates. Instructions are in English (small models follow English
instructions most reliably) but the answer language and the citation format
are set per question."""

from __future__ import annotations

from marjaa.schemas import Chunk, Language

NOT_FOUND: dict[Language, str] = {
    "en": "Not found in the provided laws.",
    "ar": "لم يتم العثور على إجابة في القوانين المتاحة.",
}
LANGUAGE_NAME: dict[Language, str] = {"en": "English", "ar": "Arabic (Modern Standard Arabic)"}

# A one-shot example of the exact output shape. Small models copy a format from
# an example far more reliably than from a rule (answers with a citation rose
# from 79% to 97%; see evals/results/). The example is deliberately about
# something no labour-law answer could contain (park opening hours): an earlier
# example about "10 days of study leave" was copied verbatim into an answer to a
# short question. `example_leaked()` checks every eval answer for this.
FORMAT_EXAMPLE: dict[Language, str] = {
    "en": (
        "Public parks open at six in the morning [Parks Example Law, Article 3]. "
        "Dogs must be kept on a lead [Parks Example Law, Article 4]."
    ),
    "ar": (
        "تفتح الحدائق العامة أبوابها في السادسة صباحًا [قانون الحدائق المثال، المادة 3]. "
        "ويجب إبقاء الكلاب مربوطة [قانون الحدائق المثال، المادة 4]."
    ),
}
_EXAMPLE_MARKERS = ("park", "dog", "الحدائق", "الحديقة", "الكلاب", "example law")


def example_leaked(answer: str) -> bool:
    """True if content from the format example ended up in a real answer."""
    text = answer.lower()
    return any(marker in text for marker in _EXAMPLE_MARKERS)


def citation_for(chunk: Chunk, lang: Language) -> str:
    """Citation label in the *answer* language, e.g. [Federal Labour Law, Article 30]."""
    if chunk.article is None:
        return f"[{chunk.law_name_ar if lang == 'ar' else chunk.law_name_en}]"
    if lang == "ar":
        return f"[{chunk.law_name_ar}، المادة {chunk.article}]"
    return f"[{chunk.law_name_en}, Article {chunk.article}]"


def system_prompt(lang: Language, example_citation: str) -> str:
    return f"""You are Marjaa (مرجع), an assistant that explains UAE law using ONLY the legal sources given to you.

Rules:
1. Write the whole answer in {LANGUAGE_NAME[lang]}.
2. After every sentence that states a legal rule, add the citation of the source it comes from, copied exactly from the source's citation attribute, for example {example_citation}. Only cite sources listed below. Never invent article numbers.
3. If the sources do not answer the question, reply with exactly this sentence and nothing else: {NOT_FOUND[lang]}
4. Be concise: 2 to 6 sentences, or a short list. Copy numbers (days, amounts, percentages) exactly as they appear in the sources.
5. Explain what the law says; do not give personal legal advice.

Format example (made-up law, shows the shape only; use the citations of YOUR sources):
{FORMAT_EXAMPLE[lang]}"""


def user_prompt(question: str, chunks: list[Chunk], lang: Language) -> str:
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        doc_lang = "Arabic" if chunk.language == "ar" else "English"
        blocks.append(
            f'<source id="{i}" citation="{citation_for(chunk, lang)}" language="{doc_lang}">\n'
            f"{chunk.text}\n</source>"
        )
    sources = "\n\n".join(blocks)
    # Repeating the rule right before generation (recency) helps small models.
    first = citation_for(chunks[0], lang) if chunks else ""
    return (
        f"Sources:\n{sources}\n\nQuestion: {question}\n\n"
        f"Answer in {LANGUAGE_NAME[lang]}. End EVERY sentence with its citation, "
        f"for example {first}."
    )
