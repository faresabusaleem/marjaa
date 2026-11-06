"""Hugging Face Space entry point (Gradio SDK on free ZeroGPU hardware).

Free accounts can no longer host CPU Gradio/Docker Spaces, but can host up to
2 ZeroGPU Spaces. So:
- query embedding + reranking (the only GPU work) run inside @spaces.GPU,
  which borrows a GPU for a few seconds per question;
- generation uses the free Gemini API (set GEMINI_API_KEY as a Space secret),
  outside the GPU function so it does not use GPU quota;
- the index is pre-built locally (`make space`) and shipped with the Space.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ.setdefault("MARJAA_LLM_PROVIDER", "gemini")
os.environ.setdefault("MARJAA_SAVE_TRACES", "false")

import spaces
import torch

if torch.cuda.is_available():
    # ZeroGPU emulates CUDA at import time; models must be placed on "cuda" here.
    os.environ.setdefault("MARJAA_DEVICE", "cuda")

from marjaa.service import get_pipeline
from marjaa.ui.app import UI_CSS, UI_HEAD, build_ui, theme

pipeline = get_pipeline()
_retrieve = pipeline.retriever.retrieve


@spaces.GPU(duration=30)
def gpu_retrieve(*args, **kwargs):
    return _retrieve(*args, **kwargs)


pipeline.retriever.retrieve = gpu_retrieve  # type: ignore[method-assign]

demo = build_ui(lambda: pipeline)
demo.queue(default_concurrency_limit=4).launch(css=UI_CSS, head=UI_HEAD, theme=theme())
