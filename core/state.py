# core/state.py
"""
Core state model.

Rules:
- core/ must not import streamlit.
- RunState is the single source of truth, stored by the UI under st.session_state["run"].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


from core.models import AlignmentResult, ComputedProfiles, InputSet


def utc_now() -> datetime:
    """Timezone-aware UTC timestamp helper."""
    return datetime.now(timezone.utc)


class Phase(str, Enum):
    INPUT = "input"
    ALIGNMENT = "alignment"
    VISUALIZATION = "visualization"


@dataclass(frozen=True, slots=True)
class LogEvent:
    """
    Append-only event record for reproducibility / transparency.

    Keep this small:
    - data should be JSON-serializable (or stringified in export).
    """

    ts_utc: datetime
    level: str
    event: str
    data: dict[str, Any]

    @classmethod
    def now(cls, *, level: str, event: str, data: dict[str, Any]) -> "LogEvent":
        return cls(ts_utc=utc_now(), level=level, event=event, data=data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts_utc.isoformat(timespec="seconds"),
            "level": self.level,
            "event": self.event,
            "data": self.data,
        }


@dataclass(slots=True)
class RunState:
    """
    Single-run state for one analysis session.
    """

    run_id: str
    created_at_utc: datetime
    phase: Phase = Phase.INPUT

    # Append-only reproducibility log (in-memory)
    events: list[LogEvent] = field(default_factory=list)

    # Committed artifacts
    input_set: InputSet | None = None
    alignment_result: AlignmentResult | None = None
    computed_profiles: ComputedProfiles | None = None

    # Simple single-run locks
    inputs_locked: bool = False
    alignment_locked: bool = False
    profiles_locked: bool = False

    @classmethod
    def new(cls) -> "RunState":
        return cls(
            run_id=uuid.uuid4().hex,
            created_at_utc=utc_now(),
            phase=Phase.INPUT,
        )

    def log(self, *, event: str, data: dict[str, Any] | None = None, level: str = "INFO") -> None:
        """Single entry point: adds timestamp automatically."""
        self.events.append(LogEvent.now(level=level, event=event, data=data or {}))
