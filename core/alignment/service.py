from __future__ import annotations

import uuid
from datetime import UTC, datetime

from core.analysis_session_models import (
    AlignedSequence,
    AlignmentStage,
    AlignmentStatus,
    AnalysisSession,
    AnalysisStage,
)
from core.constants import GAP_CHAR, STANDARD_AMINO_ACIDS
from core.provenance_log import append_event
from integrations.mafft import MAFFT_TIMEOUT_SECONDS, run_mafft

_ALLOWED_ALIGNED: frozenset[str] = frozenset(STANDARD_AMINO_ACIDS) | {GAP_CHAR}
_MAFFT_ARGS: list[str] = ["--auto", "--amino", "--inputorder", "--quiet", "--thread", "1"]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_fasta(text: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    header: str | None = None
    seq_parts: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(seq_parts)))
            header = line[1:].split()[0]
            seq_parts = []
        elif line.strip():
            seq_parts.append(line.strip())
    if header is not None:
        records.append((header, "".join(seq_parts)))
    return records


def _make_error_stage(
    error_summary: str,
    stdout: str,
    stderr: str,
    stdout_truncated: bool,
    stderr_truncated: bool,
    exit_code: int | None,
) -> AlignmentStage:
    return AlignmentStage(
        status=AlignmentStatus.ERROR,
        aligner="MAFFT",
        mafft_mode="auto",
        mafft_args=_MAFFT_ARGS,
        mafft_timeout_seconds=MAFFT_TIMEOUT_SECONDS,
        mafft_exit_code=exit_code,
        mafft_stdout_snippet=stdout,
        mafft_stderr_snippet=stderr,
        mafft_stdout_truncated=stdout_truncated,
        mafft_stderr_truncated=stderr_truncated,
        error_summary=error_summary,
    )


def run_alignment(session: AnalysisSession) -> tuple[bool, str | None]:
    if len(session.input_stage.selected_sequences) < 2:
        return False, "At least 2 selected sequences are required. Complete Step 1 first."

    if session.alignment_stage.status == AlignmentStatus.SUCCESS:
        return False, "A valid alignment already exists. Reopen alignment to run again."

    sequences = session.input_stage.selected_sequences
    fasta_input = "\n".join(f">{seq.id}\n{seq.sequence}" for seq in sequences) + "\n"

    stdout, stderr, return_code, stdout_truncated, stderr_truncated = run_mafft(fasta_input)

    def _fail(msg: str) -> tuple[bool, str]:
        session.alignment_stage = _make_error_stage(
            msg, stdout, stderr, stdout_truncated, stderr_truncated, return_code
        )
        append_event(session, "alignment_run", {
            "status": "failed",
            "aligner": "MAFFT",
            "mafft_args": _MAFFT_ARGS,
            "timeout_seconds": MAFFT_TIMEOUT_SECONDS,
            "error_summary": msg,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        })
        session.updated_at = _utc_now()
        return False, msg

    if return_code != 0:
        return _fail(f"MAFFT exited with code {return_code}.")

    parsed = _parse_fasta(stdout)

    if len(parsed) != len(sequences):
        return _fail(
            f"MAFFT returned {len(parsed)} sequences, expected {len(sequences)}."
        )

    seq_index = {seq.id: seq for seq in sequences}
    aligned_seqs: list[AlignedSequence] = []
    alignment_length: int | None = None

    for header, aligned_seq_raw in parsed:
        input_seq = seq_index.get(header)
        if input_seq is None:
            return _fail(f"MAFFT returned unexpected sequence ID '{header}'.")

        aligned_seq = aligned_seq_raw.upper()

        invalid_chars = {c for c in aligned_seq if c not in _ALLOWED_ALIGNED}
        if invalid_chars:
            return _fail(
                f"MAFFT output for '{header}' contains invalid characters:"
                f" {sorted(invalid_chars)}."
            )

        if alignment_length is None:
            alignment_length = len(aligned_seq)
        elif len(aligned_seq) != alignment_length:
            return _fail("MAFFT output sequences have inconsistent lengths.")

        aligned_seqs.append(
            AlignedSequence(
                id=_new_id("alnseq"),
                input_sequence_id=input_seq.id,
                name=input_seq.name,
                aligned_sequence=aligned_seq,
            )
        )

    if not alignment_length:
        return _fail("MAFFT produced an empty alignment.")

    now = _utc_now()
    session.alignment_stage = AlignmentStage(
        status=AlignmentStatus.SUCCESS,
        aligner="MAFFT",
        mafft_mode="auto",
        mafft_args=_MAFFT_ARGS,
        mafft_timeout_seconds=MAFFT_TIMEOUT_SECONDS,
        mafft_exit_code=return_code,
        mafft_stdout_snippet=stdout,
        mafft_stderr_snippet=stderr,
        mafft_stdout_truncated=stdout_truncated,
        mafft_stderr_truncated=stderr_truncated,
        aligned_sequences=aligned_seqs,
        alignment_length=alignment_length,
        completed_at=now,
    )
    append_event(session, "alignment_run", {
        "status": "succeeded",
        "aligner": "MAFFT",
        "mafft_args": _MAFFT_ARGS,
        "timeout_seconds": MAFFT_TIMEOUT_SECONDS,
        "aligned_sequence_count": len(aligned_seqs),
        "alignment_length": alignment_length,
    })
    session.updated_at = now

    return True, None


def reopen_alignment(session: AnalysisSession) -> None:
    session.alignment_stage = AlignmentStage()
    session.analysis_stage = AnalysisStage()
    append_event(session, "downstream_state_cleared", {
        "reason": "alignment_recomputed",
        "cleared_alignment": True,
        "cleared_analysis": True,
        "cleared_annotations": True,
    })
    session.updated_at = _utc_now()
