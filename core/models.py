from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


InputKind = Literal["fasta_aa", "fasta_nt", "genbank_id", "raw_aa", "raw_nt"]


@dataclass(frozen=True, slots=True)
class InputEntry:
    """
    A single user-provided input item.

    Note:
    - This is a pure DTO. No validation or parsing logic here.
    - `sequence` may be empty for `genbank_id` inputs until retrieval exists.
    """

    entry_id: str
    kind: InputKind

    # Human-facing identification
    name: str
    description: str | None = None

    # Content / reference
    sequence: str | None = None
    genbank_id: str | None = None

    # Optional metadata (export-friendly, not required for MVP)
    organism: str | None = None
    taxonomy: str | None = None


@dataclass(frozen=True, slots=True)
class InputSet:
    """
    Committed user inputs (immutable snapshot).
    """

    entries: list[InputEntry]
    committed_at: datetime

    # Convenience export metadata
    entry_count: int
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class AlignmentParams:
    """
    MAFFT v7 parameters (export + reproducibility).

    Keep minimal: include only what you will actually set in the MVP.
    """

    algorithm: str = "auto"
    threads: int = 1
    maxiterate: int | None = None
    use_fast: bool = False

    # If you later add extra flags, include them here for reproducibility.
    extra_args: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AlignmentExecution:
    """
    Structured execution record for an integration call (MAFFT).

    Store previews only in state; full logs should be written to files by integrations.
    """

    command: list[str]
    started_at: datetime
    finished_at: datetime

    return_code: int
    stdout_preview: str | None = None
    stderr_preview: str | None = None

    # Export-friendly optional fields
    duration_seconds: float | None = None
    tool_name: str = "mafft"
    tool_version: str | None = None


@dataclass(frozen=True, slots=True)
class AlignedSequence:
    """
    A single aligned sequence (FASTA-style record) after alignment.
    """

    seq_id: str
    description: str | None
    aligned_sequence: str

    original_length: int | None = None
    aligned_length: int | None = None


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    """
    Result of alignment step.

    The aligned sequences are stored directly for MVP.
    If later too large, you can move full alignment to a file and keep only a reference.
    """

    params: AlignmentParams
    execution: AlignmentExecution

    sequences: list[AlignedSequence]
    alignment_length: int

    created_at: datetime


@dataclass(frozen=True, slots=True)
class ComputedProfiles:
    """
    Deterministic computed profiles over alignment columns.

    All arrays are expected to be aligned by `positions_1based`.
    """

    computed_at: datetime
    alignment_length: int
    positions_1based: list[int]

    # Main profiles (1 value per alignment column)
    hydropathy: list[float] | None = None
    polar_requirement: list[float] | None = None

    # Composition summaries (1 value per column)
    gap_fraction: list[float] | None = None

    # Optional: per-AA fraction per column. Keys are single-letter residues.
    aa_fraction: dict[str, list[float]] | None = None

    # Export metadata for reproducibility
    method_name: str = "profiles_v1"
    method_version: str | None = None


@dataclass(frozen=True, slots=True)
class RegionAnnotation:
    """
    User-provided or derived region annotation in alignment column coordinates (1-based, inclusive).
    """

    label: str
    start_col_1based: int
    end_col_1based: int

    kind: str | None = None  # e.g., "domain", "motif", "region"
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ExportResult:
    """
    Filesystem export summary (created by integrations/files.py).
    """

    created_at: datetime
    export_path: str

    included_files: list[str] = field(default_factory=list)
    total_bytes: int | None = None
