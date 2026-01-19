"""
Run factory (core-only).

Central place to create a new RunState and append the mandatory 'session_start' event.

Rules:
- No Streamlit imports.
- No filesystem writes.
"""

from __future__ import annotations

from core.provenance import append_event, session_start_payload
from core.state import RunState


def create_new_run() -> RunState:
    run = RunState.new()
    append_event(
        run=run,
        event="session_start",
        data=session_start_payload(),
        level="INFO",
    )
    return run
