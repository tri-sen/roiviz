"""
Core state model (Step 1).

Rules:
- core/ must not import streamlit.
- RunState is the single source of truth, stored by the UI under st.session_state["run"].
- Step 1: we only model run identity, phase, and an in-memory append-only event log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


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

    Step 1 fields:
    - run_id: new UUID per run
    - phase: starts in INPUT
    - events: append-only list of LogEvent
    """

    run_id: str
    created_at_utc: datetime
    phase: Phase = Phase.INPUT

    events: list[LogEvent] = field(default_factory=list)

    @classmethod
    def new(cls) -> "RunState":
        return cls(
            run_id=uuid.uuid4().hex,
            created_at_utc=datetime.now(timezone.utc),
            phase=Phase.INPUT,
            events=[],
        )
