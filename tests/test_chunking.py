from marjaa.config import Settings
from marjaa.ingest.chunking import article_chunks, find_articles, fixed_chunks
from marjaa.ingest.pipeline import load_chunks, parse_all, run_ingest
from marjaa.schemas import LawInfo, Page, ParsedDocument

LAW = LawInfo(id="t", name_en="Test Law", name_ar="قانون الاختبار")


def _doc(text: str, lang: str = "en") -> ParsedDocument:
    pages = [Page(number=i + 1, text=t) for i, t in enumerate(text.split("\f"))]
    return ParsedDocument(law=LAW, language=lang, source_file="t.pdf", parser="x", pages=pages)


def test_cross_references_are_not_article_headings() -> None:
    text = (
        "Preamble\nArticle (1)\nScope\nAs per\nArticle (5) of this Law applies.\nArticle (2)\nEnd"
    )
    spans = find_articles(text, "en")
    assert [s.number for s in spans] == [None, 1, 2]


def test_out_of_sequence_numbers_are_ignored() -> None:
    text = "Article (1)\nA\nArticle (40)\nnot a heading\nArticle (2)\nB"
    assert [s.number for s in find_articles(text, "en")] == [1, 2]


def test_arabic_headings_with_arabic_indic_digits() -> None:
    text = "المادة (١)\nنص\nالمادة 2\nنص آخر"
    assert [s.number for s in find_articles(text, "ar")] == [1, 2]


def test_article_chunks_track_pages_and_chapters() -> None:
    doc = _doc("Chapter One\nGeneral\nArticle (1)\nFirst text.\fArticle (2)\nSecond text.")
    chunks = article_chunks(doc)
    assert [c.article for c in chunks] == [1, 2]
    assert chunks[0].chapter == "Chapter One: General"
    assert chunks[0].page_start == 1 and chunks[1].page_start == 2
    assert chunks[1].citation == "[Test Law, Article 2]"


def test_long_articles_are_sub_split_with_heading_repeated() -> None:
    body = "\n".join(f"{i}. " + "word " * 40 for i in range(10))
    chunks = article_chunks(_doc(f"Article (1)\n{body}"), max_chars=500)
    assert len(chunks) > 1
    assert all(c.text.startswith("Article (1)") and c.article == 1 for c in chunks)
    assert [c.part for c in chunks] == list(range(len(chunks)))


def test_fixed_chunks_overlap_and_record_articles() -> None:
    text = "\n".join(f"Article ({i})\n" + "text " * 60 for i in range(1, 6))
    chunks = fixed_chunks(_doc(text), size=400, overlap=100)
    assert len(chunks) > 3
    assert all(c.articles for c in chunks)
    covered = {a for c in chunks for a in c.articles}
    assert covered == {1, 2, 3, 4, 5}


def test_arabic_citation_format() -> None:
    doc = _doc("المادة (1)\nنص", lang="ar")
    assert article_chunks(doc)[0].citation == "[قانون الاختبار، المادة 1]"


def test_pipeline_on_fixture_law(settings: Settings) -> None:
    docs = parse_all(settings)
    assert {d.language for d in docs} == {"ar", "en"}
    counts = run_ingest(settings)
    assert counts["article"] >= 12  # 6 articles x 2 languages (+ preambles)
    chunks = load_chunks(settings, "article")
    ar5 = next(c for c in chunks if c.language == "ar" and c.article == 5)
    assert "إجازة وضع" in ar5.text
    assert ar5.chapter.startswith("الفصل الثاني")
    # Chapter headings must not leak into the previous article's text.
    ar2 = next(c for c in chunks if c.language == "ar" and c.article == 2)
    assert "الفصل الثاني" not in ar2.text


def test_mirrored_brackets_and_titles() -> None:
    doc = _doc(
        "Article )1 (\nAnnual leave\n1. The Worker gets leave.\nArticle )2(\nSick leave\nText."
    )
    chunks = article_chunks(doc)
    assert [c.text.split("\n")[0] for c in chunks] == ["Article (1)", "Article (2)"]
    assert [c.title for c in chunks] == ["Annual leave", "Sick leave"]
    assert chunks[0].header == "Test Law | Annual leave"


def test_sub_split_parts_repeat_title() -> None:
    body = "\n".join(f"{i}. " + "word " * 40 for i in range(10))
    chunks = article_chunks(_doc(f"Article (1)\nProbation period\n{body}"), max_chars=500)
    assert len(chunks) > 1
    assert all(c.text.startswith("Article (1)\nProbation period\n") for c in chunks)
    assert all(len(c.text) <= 500 for c in chunks)
