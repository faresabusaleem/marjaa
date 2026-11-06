import pytest

gr = pytest.importorskip("gradio")

from marjaa.generation.citations import Citation  # noqa: E402
from marjaa.ui.app import build_ui, render_answer, render_sources  # noqa: E402


def test_render_answer_links_valid_and_flags_invalid_citations() -> None:
    answer = (
        "Leave is 30 days [Law, Article 30]. Fines apply [Law, Article 99].\n<script>x</script>"
    )
    cites = [
        Citation(
            text="[Law, Article 30]", law_id="l", article=30, valid=True, chunk_id="l-en-a030-p0"
        ),
        Citation(text="[Law, Article 99]", law_id="l", article=99, valid=False),
    ]
    out = render_answer(answer, cites)
    assert 'data-src="l-en-a030-p0"' in out
    assert 'class="cite invalid"' in out
    assert "<script>" not in out  # answer text is escaped
    assert 'dir="auto"' in out


def test_render_arabic_citation_link() -> None:
    answer = "يستحق العامل إجازة [القانون، المادة ٢٩]"
    cites = [
        Citation(text="[القانون، المادة ٢٩]", law_id="l", article=29, valid=True, chunk_id="c29")
    ]
    assert 'data-src="c29"' in render_answer(answer, cites)


def test_render_sources_sets_direction() -> None:
    src = {
        "id": "x",
        "citation": "[ق، المادة 1]",
        "language": "ar",
        "page_start": 2,
        "page_end": 3,
        "score": 0.9,
        "text": "نص",
    }
    out = render_sources([src])
    assert 'id="src-x"' in out and 'dir="rtl"' in out and "p. 2–3" in out


def test_build_ui() -> None:
    assert isinstance(build_ui(lambda: None), gr.Blocks)  # type: ignore[arg-type]
