from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.analysis_session_models import (
    AlignmentStage,
    AnalysisSession,
    AnalysisStage,
    InputSequence,
    InputSource,
    InputStage,
    ProteinCandidate,
    SourceType,
)
from core.constants import STANDARD_AMINO_ACIDS
from core.provenance_log import append_event

_VALID_AAS: frozenset[str] = frozenset(STANDARD_AMINO_ACIDS)

_PROVENANCE_SOURCE_TYPE: dict[SourceType, str] = {
    SourceType.MANUAL: "manual",
    SourceType.FASTA_UPLOAD: "fasta_upload",
    SourceType.GENBANK_UPLOAD: "genbank_upload",
    SourceType.NCBI_FETCH: "ncbi_fetch",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── commit data types ─────────────────────────────────────────────────────────


@dataclass
class ImportedCandidateRecord:
    """One parsed candidate belonging to an imported source."""

    temp_id: str
    original_name: str
    sequence: str
    description: str | None = None
    feature_type: str | None = None
    feature_location: str | None = None


@dataclass
class ImportedSourceRecord:
    """Metadata and full candidate list for one imported source."""

    temp_id: str
    source_type: SourceType
    filename: str | None = None
    accession: str | None = None
    all_candidates: list[ImportedCandidateRecord] = field(default_factory=list)


@dataclass
class SelectedSequenceRecord:
    """One entry in the selected-sequence list, ready for commit."""

    name: str
    sequence: str
    # Populated only for imported sequences:
    imported_source_temp_id: str | None = None
    imported_cand_temp_id: str | None = None
    imported_cand_original_name: str | None = None


# ── validation ────────────────────────────────────────────────────────────────


def validate_sequence(name: str, sequence: str) -> tuple[bool, str | None]:
    if not name or not name.strip():
        return False, "Name is required."
    normalized = sequence.strip().upper()
    if not normalized:
        return False, "Sequence is required."
    for char in normalized:
        if char == "-":
            return False, "Gaps (-) are not allowed in input sequences."
        if char == "X":
            return False, "Ambiguous residue X is not allowed."
        if char not in _VALID_AAS:
            return False, f"Invalid character '{char}'. Only the 20 standard amino acids are accepted."
    return True, None


# ── commit ────────────────────────────────────────────────────────────────────


def commit_input(
    session: AnalysisSession,
    selected_sequences: list[SelectedSequenceRecord],
    imported_sources: list[ImportedSourceRecord],
) -> tuple[bool, str | None]:
    """Validate and commit all selected sequences (manual and imported) to the session."""
    if len(selected_sequences) < 2:
        return False, "At least 2 sequences are required."
    if len(selected_sequences) > 6:
        return False, "At most 6 sequences are allowed."

    names = [s.name.strip() for s in selected_sequences]
    if len(set(names)) != len(names):
        return False, "Sequence names must be unique."

    for s in selected_sequences:
        ok, err = validate_sequence(s.name, s.sequence)
        if not ok:
            return False, f"Sequence '{s.name.strip() or '(unnamed)'}': {err}"

    # Determine which imported sources have at least one selected sequence.
    used_source_ids: set[str] = set()
    for s in selected_sequences:
        if s.imported_source_temp_id:
            used_source_ids.add(s.imported_source_temp_id)

    now = _utc_now()

    # Build InputSource objects and flat candidate list for used imported sources.
    sources: list[InputSource] = []
    all_candidates: list[ProteinCandidate] = []
    temp_to_real_source_id: dict[str, str] = {}
    temp_to_real_cand_id: dict[tuple[str, str], str] = {}

    for src_data in imported_sources:
        if src_data.temp_id not in used_source_ids:
            continue

        real_src_id = _new_id("src")
        temp_to_real_source_id[src_data.temp_id] = real_src_id

        if src_data.source_type in (SourceType.FASTA_UPLOAD, SourceType.GENBANK_UPLOAD):
            display_label = src_data.filename
        elif src_data.source_type == SourceType.NCBI_FETCH:
            display_label = src_data.accession
        else:
            display_label = None

        sources.append(
            InputSource(
                id=real_src_id,
                source_type=src_data.source_type,
                display_label=display_label,
                filename=src_data.filename,
                accession=src_data.accession,
                imported_at=now,
            )
        )

        for c in src_data.all_candidates:
            real_cand_id = _new_id("cand")
            temp_to_real_cand_id[(src_data.temp_id, c.temp_id)] = real_cand_id
            all_candidates.append(
                ProteinCandidate(
                    id=real_cand_id,
                    source_id=real_src_id,
                    name=c.original_name,
                    sequence=c.sequence,
                    description=c.description,
                    feature_type=c.feature_type,
                    feature_location=c.feature_location,
                )
            )

    # Create InputSequence entries (and manual InputSource+ProteinCandidate
    # pairs) for each selected sequence.
    input_sequences: list[InputSequence] = []
    for s in selected_sequences:
        normalized_name = s.name.strip()
        normalized_seq = s.sequence.strip().upper()
        seq_id = _new_id("seq")

        if s.imported_source_temp_id:
            real_src_id = temp_to_real_source_id[s.imported_source_temp_id]
            real_cand_id = temp_to_real_cand_id[
                (s.imported_source_temp_id, s.imported_cand_temp_id)
            ]
            input_sequences.append(
                InputSequence(
                    id=seq_id,
                    source_id=real_src_id,
                    candidate_id=real_cand_id,
                    name=normalized_name,
                    sequence=normalized_seq,
                )
            )
        else:
            src_id = _new_id("src")
            cand_id = _new_id("cand")
            sources.append(
                InputSource(
                    id=src_id,
                    source_type=SourceType.MANUAL,
                    display_label=None,
                    imported_at=now,
                )
            )
            all_candidates.append(
                ProteinCandidate(
                    id=cand_id,
                    source_id=src_id,
                    name=normalized_name,
                    sequence=normalized_seq,
                )
            )
            input_sequences.append(
                InputSequence(
                    id=seq_id,
                    source_id=src_id,
                    candidate_id=cand_id,
                    name=normalized_name,
                    sequence=normalized_seq,
                )
            )

    session.alignment_stage = AlignmentStage()
    session.analysis_stage = AnalysisStage()
    session.input_stage = InputStage(
        sources=sources,
        candidates=all_candidates,
        selected_sequences=input_sequences,
    )

    # Build a lookup for candidate count per source for provenance.
    cand_count_by_src: dict[str, int] = {}
    for cand in all_candidates:
        cand_count_by_src[cand.source_id] = cand_count_by_src.get(cand.source_id, 0) + 1

    for src in sources:
        src_payload: dict = {
            "source_id": src.id,
            "source_type": _PROVENANCE_SOURCE_TYPE[src.source_type],
            "candidate_count": cand_count_by_src.get(src.id, 0),
        }
        if src.filename:
            src_payload["filename"] = src.filename
        if src.accession:
            src_payload["accession"] = src.accession
        append_event(session, "input_source_added", src_payload)

    for seq in input_sequences:
        append_event(session, "input_selection_changed", {
            "action": "added",
            "selected_sequence_id": seq.id,
            "candidate_id": seq.candidate_id,
            "selected_sequence_count": len(input_sequences),
        })

    append_event(session, "input_accepted", {
        "selected_sequence_ids": [s.id for s in input_sequences],
        "selected_sequence_count": len(input_sequences),
    })

    session.updated_at = _utc_now()
    return True, None
