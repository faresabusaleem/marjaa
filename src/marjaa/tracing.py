"""One JSON trace per query: what was retrieved, the prompt, the answer, timings.

Traces make failures debuggable after the fact ("why did it cite Article 12?")
and double as raw material for building new eval questions.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def new_trace_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]


def save_trace(traces_dir: Path, trace_id: str, trace: dict[str, Any]) -> Path:
    day_dir = traces_dir / trace_id[:8]
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{trace_id}.json"
    path.write_text(json.dumps(trace, ensure_ascii=False, indent=2, default=str), "utf-8")
    return path
