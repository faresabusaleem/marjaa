"""Gradio front-end: RTL-aware answers with clickable citations.

Each citation in the answer is a link; clicking it opens and highlights the
cited article in the Sources panel. Text direction is set per block with
dir="auto", so Arabic renders right-to-left and English left-to-right.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterator

import gradio as gr

from marjaa.generation.answer import RagPipeline
from marjaa.generation.citations import CITATION_RE, Citation
from marjaa.ingest.normalize import to_ascii_digits

EXAMPLES = [
    "ما هي مدة الإجازة السنوية التي يستحقها العامل؟",
    "How many days of maternity leave is a female worker entitled to?",
    "What is the maximum length of the probation period?",
    "هل يجوز لصاحب العمل الاحتفاظ بالوثائق الشخصية للعامل؟",
    "How is end-of-service gratuity calculated?",
    "What is the fine for running a red light in Dubai?",
]

UI_CSS = """
.marjaa-answer, .marjaa-sources { font-size: 1.05rem; line-height: 1.8; }
.marjaa-answer [dir=rtl], .marjaa-sources [dir=rtl] {
  font-family: "Noto Naskh Arabic", "Geeza Pro", "Segoe UI", Tahoma, sans-serif; }
.marjaa-answer p { margin: 0 0 .6em; unicode-bidi: plaintext; }
a.cite { text-decoration: none; padding: 0 .25em; border-radius: 4px;
  background: var(--color-accent-soft); color: var(--color-accent); cursor: pointer;
  white-space: nowrap; }
a.cite.invalid { background: #fde8e8; color: #b42318; text-decoration: line-through; }
.src { border: 1px solid var(--border-color-primary); border-radius: 8px;
  padding: .5em .8em; margin-bottom: .5em; transition: box-shadow .3s; }
.src summary { cursor: pointer; font-weight: 600; }
.src .meta { font-weight: 400; opacity: .7; font-size: .85em; }
.src .src-text { white-space: pre-wrap; margin-top: .5em; }
.src.flash { box-shadow: 0 0 0 3px var(--color-accent); }
.abstain { opacity: .8; font-style: italic; }
"""

# Event delegation survives Gradio re-rendering the HTML on every token.
UI_HEAD = """
<script>
document.addEventListener("click", (e) => {
  const link = e.target.closest("a.cite");
  if (!link) return;
  e.preventDefault();
  const box = document.getElementById("src-" + link.dataset.src);
  if (!box) return;
  box.open = true;
  box.scrollIntoView({behavior: "smooth", block: "center"});
  box.classList.add("flash");
  setTimeout(() => box.classList.remove("flash"), 1600);
});
</script>
"""


def theme() -> gr.themes.Base:
    return gr.themes.Soft(primary_hue="teal", neutral_hue="slate")


def _paragraphs(escaped: str) -> str:
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    paras = [p for p in escaped.split("\n") if p.strip()]
    return "".join(f'<p dir="auto">{p}</p>' for p in paras)


def render_answer(
    answer: str, citations: list[Citation] | None = None, streaming: bool = False
) -> str:
    """Escape the answer and turn each citation into a link to its source."""
    by_text: dict[tuple[str, int], Citation] = {}
    for c in citations or []:
        by_text[(c.text, c.article)] = c

    def link(match: re.Match) -> str:
        raw = html.unescape(match.group(0))
        numbers = [int(to_ascii_digits(n)) for n in re.findall(r"[0-9٠-٩]+", match.group(2))]
        cites = [by_text.get((raw, n)) for n in numbers]
        target = next((c for c in cites if c and c.valid), None)
        if target:
            cid = target.chunk_id
            return f'<a class="cite" href="#src-{cid}" data-src="{cid}">{match.group(0)}</a>'
        if citations is not None and not streaming:
            title = "This article was not among the retrieved sources"
            return f'<a class="cite invalid" title="{title}">{match.group(0)}</a>'
        return match.group(0)

    body = CITATION_RE.sub(link, html.escape(answer, quote=False))
    cursor = " ▌" if streaming else ""
    return f'<div class="marjaa-answer">{_paragraphs(body + cursor)}</div>'


def render_sources(sources: list[dict]) -> str:
    if not sources:
        return '<div class="marjaa-sources"><i>No sources retrieved.</i></div>'
    blocks = []
    for s in sources:
        pages = f"p. {s['page_start']}" + (
            f"–{s['page_end']}" if s["page_end"] != s["page_start"] else ""
        )
        lang = "العربية" if s["language"] == "ar" else "English"
        direction = "rtl" if s["language"] == "ar" else "ltr"
        blocks.append(
            f'<details class="src" id="src-{s["id"]}" dir="{direction}">'
            f'<summary dir="auto">{html.escape(s["citation"])} '
            f'<span class="meta">· {lang} · {pages} · score {s["score"]:.2f}</span></summary>'
            f'<div class="src-text">{html.escape(s["text"])}</div></details>'
        )
    return '<div class="marjaa-sources">' + "".join(blocks) + "</div>"


def build_ui(get_pipeline: Callable[[], RagPipeline]) -> gr.Blocks:
    def respond(question: str) -> Iterator[tuple[str, str, str]]:
        question = (question or "").strip()
        if len(question) < 2:
            yield render_answer("Please type a question. / الرجاء كتابة سؤال."), "", ""
            return
        pipeline = get_pipeline()
        answer, sources_html = "", ""
        for event in pipeline.stream(question):
            if event["event"] == "sources":
                sources_html = render_sources(event["data"]["sources"])
                yield render_answer("…", streaming=True), sources_html, ""
            elif event["event"] == "token":
                answer += event["data"]["text"]
                yield render_answer(answer, streaming=True), sources_html, ""
            elif event["event"] == "done":
                d = event["data"]
                cites = [Citation(**c) for c in d["citations"]]
                html_answer = render_answer(d["answer"], cites)
                if d["abstained"]:
                    html_answer = html_answer.replace("marjaa-answer", "marjaa-answer abstain", 1)
                invalid = sum(not c.valid for c in cites)
                meta = (
                    f"{d['provider']}:{d['model']} · {d['latency_ms']['total'] / 1000:.1f}s · "
                    f"{len(cites)} citation(s)"
                    + (
                        f", {invalid} not verified"
                        if invalid
                        else ", all verified"
                        if cites
                        else ""
                    )
                    + f" · trace {d['trace_id']}"
                )
                yield html_answer, sources_html, meta

    with gr.Blocks(title="Marjaa · مرجع") as demo:
        gr.Markdown(
            "# Marjaa · مرجع\n"
            "Ask about the **UAE Federal Labour Law** in Arabic or English. Every answer cites the "
            "exact article; click a citation to read it.  \n"
            '<span dir="rtl">اسأل عن قانون العمل الاتحادي بالعربية أو الإنجليزية، وستحصل على إجابة '
            "موثقة برقم المادة.</span>  \n"
            "<sub>Portfolio project, not legal advice. The Arabic text is the legally "
            "authoritative version.</sub>"
        )
        with gr.Row():
            question = gr.Textbox(
                label="Question · السؤال",
                placeholder="e.g. كم مدة الإجازة السنوية؟ / How long is annual leave?",
                lines=2,
                scale=5,
                rtl=False,
                elem_classes=["marjaa-question"],
            )
            ask = gr.Button("Ask · اسأل", variant="primary", scale=1)
        gr.Examples(EXAMPLES, inputs=question)
        with gr.Row():
            with gr.Column(scale=3):
                answer = gr.HTML(label="Answer", value=render_answer(""))
                meta = gr.Markdown()
            with gr.Column(scale=2):
                gr.Markdown("### Sources · المصادر")
                sources = gr.HTML()
        for trigger in (ask.click, question.submit):
            trigger(respond, inputs=question, outputs=[answer, sources, meta])
    return demo


def main() -> None:
    from marjaa.service import get_pipeline

    build_ui(get_pipeline).launch(css=UI_CSS, head=UI_HEAD, theme=theme())


if __name__ == "__main__":
    main()
