"""
In-memory provenance (reproducibility log) helpers (Step 1).

Design:
- Append-only events stored in RunState.events (no filesystem).
- Log ONLY on explicit UI actions (button clicks).
- Export as JSONL for download.
"""

from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone
from typing import Any

from core.state import LogEvent, RunState


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value: Any) -> Any:
    """
    Convert common non-JSON values into safe representations.
    Keep conservative to avoid surprising bloat.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def append_event(run: RunState, event: str, data: dict[str, Any] | None = None, level: str = "INFO") -> None:
    """
    Append an event to the in-memory run log.
    Intended usage: call only from explicit action handlers.
    """
    safe_data = _jsonable(data or {})
    run.events.append(
        LogEvent(
            ts_utc=_utc_now(),
            level=level,
            event=event,
            data=safe_data,
        )
    )


def export_events_jsonl(events: list[LogEvent]) -> str:
    """
    Export events into JSON Lines format (one JSON object per line).
    """
    lines: list[str] = []
    for e in events:
        lines.append(json.dumps(e.to_dict(), ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def session_start_payload() -> dict[str, Any]:
    """
    Minimal environment snapshot.
    Keep small; avoid secrets.
    """
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cwd": os.getcwd(),
    }
