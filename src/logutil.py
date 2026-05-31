"""Append-only JSONL per run_id for demo / zip evidence."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_event(logs_dir: Path, run_id: str, event: dict[str, Any]) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"{run_id}.jsonl"
    row = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
