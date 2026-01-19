"""
Pipeline actions.

Rules:
- No Streamlit imports.
- Side effects live in core/integrations (MAFFT subprocess).
- Actions mutate RunState in a controlled, single-run manner.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from core.models import (
    AlignmentParams,
    AlignmentResult,
    InputEntry,
    InputSet,
    InputSource,
)
from core.provenance import append_event
from core.state import Phase, RunState
from core.validation import validate_aa_sequence, validate_name
from core.integrations.mafft import parse_aligned_fasta, run_mafft


class PipelineError(Exception):
    """Raised for illegal state transitions or invalid action calls."""


def commit_inputs(run: RunState, draft_items: list[dict[str, str]]) -> None:
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
        data={"entry_count": len(committed), "names": [e.name for e in committed]},
        level="INFO",
    )


def run_alignment(
    *,
    run: RunState,
    params: AlignmentParams,
    timeout_seconds: int = 120,
) -> None:
    """
    Run MAFFT alignment exactly once for this run.
    """
    if run.input_set is None or not run.inputs_locked:
        raise PipelineError("Inputs are not committed. Commit inputs first.")
    if run.alignment_locked or run.alignment_result is not None:
        raise PipelineError("Alignment already exists for this run. Start a New run to change it.")
    if run.phase != Phase.ALIGNMENT:
        raise PipelineError(f"Illegal state: phase must be ALIGNMENT (got {run.phase.value}).")

    append_event(
        run=run,
        event="alignment_started",
        data={"tool": params.tool, "threads": params.threads, "args": params.args},
        level="INFO",
    )

    records = [(e.name, e.aa_sequence) for e in run.input_set.entries]

    try:
        out = run_mafft(
            run_id=run.run_id,
            records=records,
            args=params.args,
            threads=params.threads,
            timeout_seconds=timeout_seconds,
        )
    except Exception as e:
        append_event(run=run, event="alignment_failed", data={"error": str(e)}, level="ERROR")
        raise

    if out.execution.return_code != 0:
        append_event(
            run=run,
            event="alignment_failed",
            data={"return_code": out.execution.return_code, "stderr_preview": out.execution.stderr_preview},
            level="ERROR",
        )
        raise PipelineError(f"MAFFT failed (return code {out.execution.return_code}). See stderr preview in log.")

    aligned = parse_aligned_fasta(out.aligned_fasta)
    if not aligned:
        append_event(run=run, event="alignment_failed", data={"reason": "empty_alignment"}, level="ERROR")
        raise PipelineError("Alignment output is empty.")

    lengths = {len(s.aligned_sequence) for s in aligned}
    if len(lengths) != 1:
        append_event(run=run, event="alignment_failed", data={"reason": "inconsistent_lengths"}, level="ERROR")
        raise PipelineError("Alignment output has inconsistent sequence lengths.")

    alignment_length = next(iter(lengths))

    run.alignment_result = AlignmentResult(
        params=params,
        execution=out.execution,
        sequences=aligned,
        alignment_length=alignment_length,
        created_at=datetime.now(timezone.utc),
    )
    run.alignment_locked = True
    run.phase = Phase.VISUALIZATION

    append_event(
        run=run,
        event="alignment_completed",
        data={"alignment_length": alignment_length, "seq_count": len(aligned)},
        level="INFO",
    )
