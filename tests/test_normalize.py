from marjaa.ingest.normalize import (
    clean_text,
    detect_language,
    normalize_for_search,
    tokenize,
)
from marjaa.ingest.parsers import fix_reversed_line, text_quality


def test_removes_diacritics_and_tatweel() -> None:
    assert normalize_for_search("العَامِلُ") == "العامل"
    assert normalize_for_search("العـــامل") == "العامل"


def test_unifies_alef_ta_marbuta_and_alef_maqsura() -> None:
    assert normalize_for_search("أجر إجازة آخر") == "اجر اجازه اخر"
    assert normalize_for_search("على مستشفى") == "علي مستشفي"


def test_converts_arabic_indic_digits() -> None:
    assert normalize_for_search("المادة (٣٠)") == "الماده (30)"
    assert normalize_for_search("۱۲") == "12"


def test_clean_text_fixes_presentation_forms_but_keeps_diacritics() -> None:
    # 'ﻻ' (U+FEFB) is a ligature glyph that PDFs often emit.
    assert clean_text("ﻻ يجوز") == "لا يجوز"
    assert clean_text("العَامِل") == "العَامِل"


def test_detect_language() -> None:
    assert detect_language("ما هي مدة الإجازة السنوية؟") == "ar"
    assert detect_language("What is the annual leave?") == "en"
    assert detect_language("Article 30 المادة ثلاثون من القانون") == "ar"


def test_tokenize_stems_and_drops_stopwords() -> None:
    assert tokenize("الإجازة السنوية في القانون") == tokenize("اجازه سنويه القانون")
    assert "the" not in tokenize("the employees")
    assert tokenize("employees") == tokenize("employee")
    assert tokenize("terminated") == tokenize("terminate")
    assert tokenize("business") == ["business"]


def test_reversed_text_is_detected_and_fixed() -> None:
    good = "يستحق العامل إجازة سنوية من صاحب العمل في المادة"
    bad = good[::-1]
    assert not text_quality(good).looks_reversed
    assert text_quality(bad).looks_reversed
    assert fix_reversed_line(bad) == good


def test_fix_reversed_line_keeps_numbers_readable() -> None:
    assert fix_reversed_line("30 ةداملا") == "المادة 30"
