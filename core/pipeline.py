"""
Pipeline actions (Step 3: commit_inputs only).

Rules:
- No Streamlit imports.
- Side effects live in core/integrations (none used yet).
- Actions mutate RunState in a controlled, single-run manner.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from core.models import InputEntry, InputSet, InputSource
from core.provenance import append_event
from core.state import Phase, RunState
from core.validation import validate_aa_sequence, validate_name


class PipelineError(Exception):
    """Raised for illegal state transitions or invalid action calls."""


def commit_inputs(run: RunState, draft_items: list[dict[str, str]]) -> None:
    """
    Commit draft input entries into an immutable InputSet and advance to ALIGNMENT.

    draft_items schema (UI-owned):
    - {"name": str, "sequence": str}
    """
    if run.phase != Phase.INPUT:
        raise PipelineError(f"Illegal state: phase must be INPUT (got {run.phase.value}).")
    if run.inputs_locked or run.input_set is not None:
        raise PipelineError("Inputs are already committed for this run. Start a New run to change inputs.")

    if not draft_items or len(draft_items) < 2:
        raise PipelineError("At least 2 sequences are required.")

    committed: list[InputEntry] = []
    errors: list[str] = []

    for i, item in enumerate(draft_items, start=1):
        name_res = validate_name(item.get("name", ""))
        seq_res = validate_aa_sequence(item.get("sequence", ""))

        if not name_res.ok:
            errors.append(f"Entry {i}: {name_res.error}")
        if not seq_res.ok:
            errors.append(f"Entry {i}: {seq_res.error}")

        if name_res.ok and seq_res.ok:
            committed.append(
                InputEntry(
                    entry_id=uuid.uuid4().hex,
                    name=name_res.normalized,
                    aa_sequence=seq_res.normalized,
                    source=InputSource.MANUAL_AA,
                )
            )

    if errors:
        raise PipelineError("Cannot commit inputs:\n- " + "\n- ".join(errors))

    input_set = InputSet(entries=committed, committed_at=datetime.now(timezone.utc))
    run.input_set = input_set
    run.inputs_locked = True
    run.phase = Phase.ALIGNMENT

    append_event(
        run=run,
        event="inputs_committed",
        data={
            "entry_count": len(committed),
            "names": [e.name for e in committed],
        },
        level="INFO",
    )
