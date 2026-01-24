# core/export_models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


MediaType = Literal[
    "application/zip",
    "application/json",
    "application/x-ndjson",
    "text/csv",
    "text/plain",
    "chemical/x-fasta",
    "text/html",
]


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    """
    One file inside the export bundle (ZIP).

    Notes:
    - `zip_path` is the path inside the zip (e.g. "data/alignment.fasta").
    - `sha256` is optional, but recommended for integrity checks.
    """
    zip_path: str
    media_type: MediaType
    bytes_size: int | None = None
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ExportManifest:
    """
    Machine-readable description of the exported run.

    Keep this stable: downstream tools / reviewers will rely on it.
    """
    manifest_version: str
    created_at: datetime

    run_id: str

    # High-level run context (minimal, but useful)
    input_count: int
    alignment_length: int | None = None

    # Tool + method identifiers (strings, not code objects)
    mafft_version: str | None = None
    mafft_command: list[str] | None = None

    hp_scale_id: str | None = None
    pr_scale_id: str | None = None

    # File inventory
    artifacts: list[ExportArtifact] = field(default_factory=list)

    # Freeform notes (optional)
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ExportBundle:
    """
    Result of export creation.

    `zip_file_path` points to a local temporary file (e.g. /tmp/<run_id>/export_...zip).
    UI will offer it as download; no persistence guarantees.
    """
    created_at: datetime
    zip_file_path: str
    zip_bytes_size: int | None = None
    manifest: ExportManifest | None = None
