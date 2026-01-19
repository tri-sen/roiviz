"""
Core state model (Step 1 + Step 3 + Step 4 foundation).

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
    - committed artifacts (inputs, then alignment, then profiles later)
    """

    run_id: str
    created_at_utc: datetime
    phase: Phase = Phase.INPUT

    # Append-only reproducibility log (in-memory)
    events: list[LogEvent] = field(default_factory=list)

    # Committed artifacts
    input_set: InputSet | None = None
    alignment_result: AlignmentResult | None = None

    # Simple single-run locks
    inputs_locked: bool = False
    alignment_locked: bool = False

    computed_profiles: ComputedProfiles | None = None
    profiles_locked: bool = False

    @classmethod
    def new(cls) -> "RunState":
        return cls(
            run_id=uuid.uuid4().hex,
            created_at_utc=datetime.now(timezone.utc),
            phase=Phase.INPUT,
            events=[],
            input_set=None,
            alignment_result=None,
            inputs_locked=False,
            alignment_locked=False,
            computed_profiles=None,
            profiles_locked=False,
        )
