"""Choose the "not found" threshold on the DEV split only.

The cut-off on the reranker's top score is tuned here and then frozen, so the
answer evaluation on the TEST split is not tuned on its own data.

Usage: uv run python -m evals.runners.calibrate
"""

from __future__ import annotations

import json

from marjaa.config import get_settings
from marjaa.evaluation.dataset import load_testset
from marjaa.evaluation.experiments import calibrate_threshold, write_json
from marjaa.logging_utils import setup_logging
from marjaa.retrieval.retriever import build_retriever


def main() -> None:
    setup_logging()
    settings = get_settings()
    dev = [i for i in load_testset(settings.testset_path) if i.split == "dev"]
    result = calibrate_threshold(build_retriever(settings), dev)
    result["split"] = "dev"
    write_json(settings.results_dir / "threshold.json", result)
    print(json.dumps({k: v for k, v in result.items() if not k.endswith("scores")}, indent=2))


if __name__ == "__main__":
    main()
