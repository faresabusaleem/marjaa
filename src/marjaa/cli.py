"""Command line entry point: `uv run marjaa --help`."""

from __future__ import annotations

import json

import typer

from marjaa.config import get_settings
from marjaa.logging_utils import setup_logging

app = typer.Typer(help="Marjaa (مرجع): cited answers over UAE law.", no_args_is_help=True)


@app.command()
def ingest(
    parser: str = typer.Option("auto", help="auto (pick cleanest) | pypdf | pymupdf | pdfplumber"),
) -> None:
    """Parse data/raw/, chunk (article + fixed) and build the vector indexes."""
    from marjaa.ingest.pipeline import run_ingest
    from marjaa.retrieval.retriever import build_retriever

    setup_logging()
    settings = get_settings()
    counts = run_ingest(settings, parser)
    for strategy in ("article", "fixed"):
        build_retriever(settings, strategy)  # embeds and stores vectors
    typer.echo(json.dumps(counts))


@app.command("build-hosted")
def build_hosted() -> None:
    """Copy the article chunks into marjaa/hosted/ and embed them with Gemini.

    Run after `ingest`. The output is committed: the hosted API only reads it.
    """
    import shutil

    from marjaa.config import Settings
    from marjaa.ingest.pipeline import chunks_path
    from marjaa.retrieval.retriever import build_retriever

    setup_logging()
    local, hosted = Settings(profile="local"), Settings(profile="hosted")
    target = chunks_path(hosted, "article")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(chunks_path(local, "article"), target)
    retriever = build_retriever(hosted, "article")
    typer.echo(
        f"{len(retriever.chunks)} chunks embedded with {hosted.embedder_label} -> {target.parent}"
    )


@app.command()
def ask(question: str, show_sources: bool = False) -> None:
    """Ask one question and stream the answer to the terminal."""
    from marjaa.service import get_pipeline

    setup_logging("WARNING")
    pipeline = get_pipeline()
    for event in pipeline.stream(question):
        if event["event"] == "sources" and show_sources:
            for s in event["data"]["sources"]:
                typer.echo(f"  {s['citation']} ({s['language']}, score {s['score']:.3f})")
        elif event["event"] == "token":
            typer.echo(event["data"]["text"], nl=False)
        elif event["event"] == "done":
            d = event["data"]
            bad = [c["text"] for c in d["citations"] if not c["valid"]]
            typer.echo(f"\n\n[{d['latency_ms']['total'] / 1000:.1f}s, trace {d['trace_id']}]")
            if bad:
                typer.echo(f"Unverified citations: {bad}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, ui: bool = True) -> None:
    """Run the API (and the Gradio UI at /ui)."""
    import uvicorn

    from marjaa.api.app import create_app

    setup_logging()
    uvicorn.run(create_app(with_ui=ui), host=host, port=port, log_config=None)


if __name__ == "__main__":
    app()
