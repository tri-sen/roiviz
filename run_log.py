# core/run_log.py
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(x: Any) -> Any:
    """
    Convert common Python objects into JSON-serializable structures.
    This is intentionally conservative: if something is unknown, we fall back to repr().
    """
    if x is None or isinstance(x, (str, int, float, bool)):
        return x

    if isinstance(x, datetime):
        return x.isoformat(timespec="seconds")

    if isinstance(x, Enum):
        return x.value

    if is_dataclass(x):
        return _json_safe(asdict(x))

    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}

    if isinstance(x, (list, tuple, set)):
        return [_json_safe(v) for v in x]

    # Fallback: keep it readable, but safe
    return repr(x)


def run_log(run: Any, event: str, data: dict[str, Any] | None = None, level: str = "INFO") -> None:
    """
    Append an event to run.events without the caller caring about timestamps / serialization.

    Requirements:
    - run.events exists and is a list
    - core.state.LogEvent exists (imported lazily to avoid cyclic imports)
    """
    if data is None:
        data = {}

    if not hasattr(run, "events") or not isinstance(run.events, list):
        raise RuntimeError("RunState has no 'events' list. Ensure RunState.events exists.")

    # Lazy import to avoid cycles
    from core.state import LogEvent  # noqa: WPS433

    run.events.append(
        LogEvent(
            ts_utc=utc_now(),
            level=str(level),
            event=str(event),
            data=_json_safe(data),
        )
    )
