"""
MAFFT integration (side effects only).

Rules:
- No Streamlit imports.
- Side effects allowed: subprocess, temp files under /tmp.
- Return structured execution info + aligned FASTA text.
- Keep stdout/stderr previews small to avoid bloating session state.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from core.models import AlignmentExecution, AlignedSequence


_PREVIEW_LIMIT = 8_000  # characters


@dataclass(frozen=True, slots=True)
class MafftRunOutput:
    execution: AlignmentExecution
    aligned_fasta: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _preview(text: str | None) -> str | None:
    if not text:
        return None
    if len(text) <= _PREVIEW_LIMIT:
        return text
    # keep head+tail for debugging
    head = text[:4000]
    tail = text[-4000:]
    return head + "\n...\n" + tail


def _to_fasta(records: Iterable[tuple[str, str]]) -> str:
    lines: list[str] = []
    for name, seq in records:
        safe_name = name.strip().replace("\n", " ").replace("\r", " ")
        lines.append(f">{safe_name}")
        # wrap for readability
        for i in range(0, len(seq), 80):
            lines.append(seq[i : i + 80])
    return "\n".join(lines) + "\n"


def get_mafft_version() -> str | None:
    try:
        cp = subprocess.run(
            ["mafft", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        out = (cp.stdout or "").strip()
        err = (cp.stderr or "").strip()
        # mafft sometimes prints version to stderr
        v = out if out else err
        return v.splitlines()[0] if v else None
    except Exception:
        return None


def run_mafft(
    *,
    run_id: str,
    records: list[tuple[str, str]],
    args: list[str] | None = None,
    threads: int = 1,
    timeout_seconds: int = 120,
) -> MafftRunOutput:
    """
    Run MAFFT on provided AA sequences.

    records: list of (name, aa_sequence) without gaps.
    args: additional MAFFT CLI args (excluding --thread, input file).
    """
    args = args or []

    started = _utc_now()
    t0 = time.time()

    fasta_in = _to_fasta(records)

    with tempfile.TemporaryDirectory(prefix=f"roiviz_{run_id}_", dir="/tmp") as tmpdir:
        in_path = os.path.join(tmpdir, "input.fasta")

        with open(in_path, "w", encoding="utf-8") as f:
            f.write(fasta_in)

        cmd = ["mafft", "--thread", str(threads), *args, in_path]

        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )

        finished = _utc_now()
        duration = time.time() - t0

        exec_rec = AlignmentExecution(
            command=cmd,
            started_at=started,
            finished_at=finished,
            return_code=cp.returncode,
            stdout_preview=_preview(cp.stdout),
            stderr_preview=_preview(cp.stderr),
            tool_name="mafft",
            tool_version=get_mafft_version(),
            duration_seconds=duration,
        )

        aligned_fasta = cp.stdout or ""
        return MafftRunOutput(execution=exec_rec, aligned_fasta=aligned_fasta)


def parse_aligned_fasta(fasta_text: str) -> list[AlignedSequence]:
    """
    Minimal FASTA parser for aligned output.
    Accepts:
    >header
    SEQ...
    """
    seqs: list[AlignedSequence] = []
    name: str | None = None
    buf: list[str] = []

    def flush():
        nonlocal name, buf
        if name is None:
            return
        s = "".join(buf).strip()
        seqs.append(
            AlignedSequence(
                seq_id=name,  # MVP: reuse name as id (stable enough for now)
                name=name,
                aligned_sequence=s,
            )
        )
        name = None
        buf = []

    for raw_line in fasta_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            flush()
            name = line[1:].strip()
        else:
            buf.append(line)

    flush()
    return seqs
