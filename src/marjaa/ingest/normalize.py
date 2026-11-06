"""Arabic/English text normalisation.

Two levels:
- `clean_text`: safe for *display*. Fixes PDF artefacts (Arabic presentation
  forms, odd whitespace) but keeps diacritics, hamza forms, etc.
- `normalize_for_search`: aggressive, used only for *matching* (BM25 tokens,
  deduplication). The same function is applied to queries and documents, so
  spelling variants such as أجر / اجر collapse to the same token.
"""

from __future__ import annotations

import re
import unicodedata

# Tashkeel (harakat), Quranic marks and the superscript alef.
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ALEF_VARIANTS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})
# Ta marbuta and alef maqsura are often typed interchangeably with ha / ya,
# so search treats them as the same letter.
_LETTER_VARIANTS = str.maketrans({"ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PUNCT = str.maketrans({"،": ",", "؛": ";", "؟": "?", "٪": "%"})
_SPACES = re.compile(r"[ \t ​-‏‪-‮⁦-⁩]+")
_ARABIC_LETTER = re.compile(r"[ء-ي]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")


def to_ascii_digits(text: str) -> str:
    return text.translate(_DIGITS)


def clean_text(text: str) -> str:
    """Display-safe cleanup: NFKC + whitespace + bidi control removal."""
    # NFKC turns Arabic presentation forms (U+FB50..U+FEFF, common in PDFs)
    # back into regular letters, e.g. 'ﻻ' -> 'لا'.
    text = unicodedata.normalize("NFKC", text)
    lines = [_SPACES.sub(" ", line).strip() for line in text.splitlines()]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def normalize_arabic(text: str) -> str:
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    return text.translate(_ALEF_VARIANTS).translate(_LETTER_VARIANTS)


def normalize_for_search(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = normalize_arabic(text)
    text = to_ascii_digits(text).translate(_PUNCT).lower()
    return _SPACES.sub(" ", text).strip()


def detect_language(text: str) -> str:
    """'ar' if most letters are Arabic, else 'en'. Good enough for routing."""
    arabic = len(_ARABIC_LETTER.findall(text))
    latin = len(_LATIN_LETTER.findall(text))
    return "ar" if arabic >= latin and arabic > 0 else "en"


# --- Tokenisation for BM25 ----------------------------------------------------

_TOKEN = re.compile(r"[\w]+", re.UNICODE)

AR_STOPWORDS = {
    normalize_for_search(w)
    for w in [
        "في",
        "من",
        "على",
        "الى",
        "إلى",
        "عن",
        "مع",
        "أو",
        "او",
        "و",
        "ثم",
        "أن",
        "ان",
        "إن",
        "هذا",
        "هذه",
        "ذلك",
        "تلك",
        "التي",
        "الذي",
        "الذين",
        "اللذين",
        "ما",
        "لا",
        "لم",
        "لن",
        "قد",
        "كان",
        "كانت",
        "يكون",
        "تكون",
        "هو",
        "هي",
        "هم",
        "كل",
        "أي",
        "اي",
        "بعد",
        "قبل",
        "عند",
        "بين",
        "حتى",
        "إذا",
        "اذا",
        "كما",
        "غير",
        "ب",
        "ل",
        "ك",
        "ف",
        "وفق",
        "وفقا",
        "بشأن",
        "لسنة",
        "رقم",
    ]
}
EN_STOPWORDS = set(
    [
        "a",
        "an",
        "the",
        "of",
        "to",
        "in",
        "on",
        "for",
        "by",
        "with",
        "at",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "or",
        "and",
        "not",
        "no",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "which",
        "who",
        "whom",
        "what",
        "when",
        "where",
        "shall",
        "may",
        "any",
        "all",
        "such",
        "than",
        "then",
        "there",
        "their",
        "his",
        "her",
        "he",
        "she",
        "they",
        "them",
        "do",
        "does",
        "did",
        "has",
        "have",
        "had",
        "into",
        "under",
        "per",
        "if",
    ]
)

# Light stemming: strip the most frequent Arabic clitics/affixes and English
# plural/verb endings. Full morphological analysis is overkill here and would
# add a heavy dependency; light stemming is the classic IR trade-off
# (cf. Larkey et al., "Light Stemming for Arabic IR").
_AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_AR_SUFFIXES = ("ها", "ان", "ات", "ون", "ين", "يه", "ه", "ي")


def _stem_ar(token: str) -> str:
    for prefix in _AR_PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 3:
            token = token[len(prefix) :]
            break
    for suffix in _AR_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            break
    return token


def _stem_en(token: str) -> str:
    for suffix, repl in (("ies", "y"), ("ing", ""), ("ed", ""), ("s", "")):
        if token.endswith(suffix) and not token.endswith("ss") and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)] + repl
            break
    # Dropping a final 'e' makes terminate/terminated and employee/employees agree.
    if token.endswith("e") and len(token) > 4:
        token = token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Normalise, split, drop stopwords and light-stem. Used for queries and docs."""
    tokens: list[str] = []
    for tok in _TOKEN.findall(normalize_for_search(text)):
        if tok in AR_STOPWORDS or tok in EN_STOPWORDS:
            continue
        if _ARABIC_LETTER.search(tok):
            tok = _stem_ar(tok)
        elif tok.isascii() and tok.isalpha():
            tok = _stem_en(tok)
        tokens.append(tok)
    return tokens
