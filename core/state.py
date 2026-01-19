"""
Core state model (Step 1 + Step 3 foundation).

Rules:
- core/ must not import streamlit.
- RunState is the single source of truth, stored by the UI under st.session_state["run"].
- Step 1: run identity + phase + in-memory append-only event log.
- Step 3 foundation: add InputSet slot and a simple lock for committed inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from core.models import InputSet


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

    Fields:
    - run identity + phase
    - append-only in-memory events
    - committed artifacts (start with InputSet)
    """

    run_id: str
    created_at_utc: datetime
    phase: Phase = Phase.INPUT

    # Append-only reproducibility log (in-memory)
    events: list[LogEvent] = field(default_factory=list)

    # Committed artifacts (Step 3 begins here)
    input_set: InputSet | None = None

    # Simple single-run locks
    inputs_locked: bool = False

    @classmethod
    def new(cls) -> "RunState":
        return cls(
            run_id=uuid.uuid4().hex,
            created_at_utc=datetime.now(timezone.utc),
            phase=Phase.INPUT,
            events=[],
            input_set=None,
            inputs_locked=False,
        )
