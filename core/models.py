"""
Core DTOs (Step 3 foundation).

Rules:
- Pure data containers only (no validation/parsing logic here).
- No Streamlit imports.
- Keep fields minimal and export-friendly.
"""

from __future__ import annotations

from dataclasses import dataclass
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
