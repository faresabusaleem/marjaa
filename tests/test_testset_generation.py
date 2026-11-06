import json

import pytest
from evals.runners.generate_testset import is_good, leaks_gold_number, parse_json_object


def test_parse_json_object_tolerates_code_fences() -> None:
    reply = '```json\n{"question": "كم مدة فترة التجربة؟", "answer": "ستة أشهر"}\n```'
    assert parse_json_object(reply)["answer"] == "ستة أشهر"
    with pytest.raises(json.JSONDecodeError):
        parse_json_object("no json here")


def test_filters_reject_label_leaks_and_wrong_language() -> None:
    ok = {"question": "كم مدة فترة التجربة القصوى؟", "answer": "ستة أشهر كحد أقصى."}
    assert is_good(ok, "ar", answerable=True)
    leak = {"question": "ماذا تنص المادة (9) بشأن التجربة؟", "answer": "ستة أشهر."}
    assert not is_good(leak, "ar", answerable=True)
    wrong_lang = {"question": "How long is probation?", "answer": "Six months."}
    assert not is_good(wrong_lang, "ar", answerable=True)


def test_gold_number_leak_is_detected() -> None:
    from marjaa.evaluation.dataset import EvalItem, GoldRef

    def item(q: str) -> EvalItem:
        return EvalItem(
            id="x",
            type="ar",
            question=q,
            question_lang="ar",
            gold=[GoldRef(law_id="l", article=74)],
        )

    assert leaks_gold_number(item("متى يبدأ العمل بالمرسوم رقم (74)؟"))
    assert not leaks_gold_number(item("متى يبدأ العمل بالمرسوم؟"))
