"""
Core DTOs.

Rules:
- Pure data containers only (no validation/parsing logic here).
- No Streamlit imports.
- Keep fields minimal and export-friendly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class InputSource(str, Enum):
    """
    Where an input sequence came from.

    Only MANUAL_AA is used in Step 3 MVP.
    Others are placeholders for later integration work.
    """

    MANUAL_AA = "manual_aa"
    FASTA_AA = "fasta_aa"
    ENTREZ_GENBANK = "entrez_genbank"
    GENBANK_UPLOAD = "genbank_upload"


@dataclass(frozen=True, slots=True)
class InputEntry:
    """
    A single committed amino-acid sequence entry.

    Notes:
    - `aa_sequence` is expected to be normalized (uppercase, stripped).
    - Validation happens in core/validation.py, not here.
    """

    entry_id: str
    name: str
    aa_sequence: str
    source: InputSource

    source_ref: str | None = None  # e.g., GenBank ID later
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class InputSet:
    """
    Immutable snapshot of committed inputs for a run.
    """

    entries: list[InputEntry]
    committed_at: datetime


# -------------------------
# Alignment DTOs (Step 4 foundation)
# -------------------------

@dataclass(frozen=True, slots=True)
class AlignmentParams:
    """
    Alignment tool parameters as actually used for a run.

    MVP: MAFFT v7 only.
    - args: CLI arguments (excluding input/output handling).
    """

    tool: str = "mafft"
    threads: int = 1
    args: list[str] = field(default_factory=list)
    label: str | None = None  # e.g. "recommended", "custom"


@dataclass(frozen=True, slots=True)
class AlignmentExecution:
    """
    Structured execution record for an integration call.

    Store previews only in state (avoid multi-MB logs).
    """

    command: list[str]
    started_at: datetime
    finished_at: datetime
    return_code: int

    stdout_preview: str | None = None
    stderr_preview: str | None = None

    tool_name: str = "mafft"
    tool_version: str | None = None
    duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class AlignedSequence:
    """
    One aligned sequence (FASTA-like record) after alignment.
    """

    seq_id: str
    name: str
    aligned_sequence: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    """
    Output of the alignment step.
    """

    params: AlignmentParams
    execution: AlignmentExecution
    sequences: list[AlignedSequence]
    alignment_length: int
    created_at: datetime

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ComputedProfiles:
    """
    Computed profiles on alignment columns using normalized HP/PR scales.

    Conventions:
    - positions are 1-based alignment columns
    - per-seq arrays contain float in [0,1] or None (unknown); GAP treated as 0.0 by compute layer
    - pairwise deltas are absolute: |Δ| in [0,1]
    """

    computed_at: datetime
    alignment_length: int
    positions_1based: list[int]

    hp_scale_id: str
    pr_scale_id: str

    # For debug / optional export
    hp_per_seq: dict[str, list[float | None]]
    pr_per_seq: dict[str, list[float | None]]

    # Pairwise absolute deltas per pair key "seqA__vs__seqB"
    hp_pairwise_delta: dict[str, list[float | None]]
    pr_pairwise_delta: dict[str, list[float | None]]

    # Summary over pairwise deltas (what Plot 1/2 use)
    hp_delta_median: list[float | None]
    hp_delta_p25: list[float | None]
    hp_delta_p75: list[float | None]

    pr_delta_median: list[float | None]
    pr_delta_p25: list[float | None]
    pr_delta_p75: list[float | None]

    # Composition
    gap_fraction: list[float]
    composition_fraction: dict[str, list[float]]

    method_name: str = "profiles_v1"
    method_version: str | None = None
