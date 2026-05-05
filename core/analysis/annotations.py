from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from core.analysis_session_models import (
    AminoAcidAnnotation,
    AnalysisSession,
    RegionAnnotation,
)
from core.constants import AMINO_ACID_THREE_LETTER, DEFAULT_REGION_ANNOTATION_COLOR, STANDARD_AMINO_ACIDS
from core.provenance_log import append_event

_MAX_NOTE_LEN = 500
_CANONICAL_AAS: frozenset[str] = frozenset(STANDARD_AMINO_ACIDS)
_COLOR_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _normalize_color_hex(color_hex: str) -> tuple[str | None, str | None]:
    if not isinstance(color_hex, str) or not _COLOR_HEX_RE.match(color_hex):
        return None, "Color must be a 6-digit hex value like #FF0000."
    return color_hex.upper(), None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _new_ann_id() -> str:
    return f"ann_{uuid.uuid4().hex[:12]}"


def add_region_annotation(
    session: AnalysisSession,
    label: str,
    start_position: int,
    end_position: int,
    alignment_length: int,
    note: str | None = None,
    color_hex: str = DEFAULT_REGION_ANNOTATION_COLOR,
) -> tuple[bool, str | None]:
    label = label.strip()
    if not label:
        return False, "Label must not be empty."
    if not (1 <= start_position <= end_position <= alignment_length):
        return False, f"Positions must satisfy 1 ≤ start ≤ end ≤ {alignment_length}."
    trimmed_note: str | None = note.strip() if note and note.strip() else None
    if trimmed_note is not None and len(trimmed_note) > _MAX_NOTE_LEN:
        return False, f"Note must not exceed {_MAX_NOTE_LEN} characters."
    normalized_color, color_err = _normalize_color_hex(color_hex)
    if normalized_color is None:
        return False, color_err

    annotation = RegionAnnotation(
        id=_new_ann_id(),
        label=label,
        start_position=start_position,
        end_position=end_position,
        note=trimmed_note,
        color_hex=normalized_color,
    )
    session.analysis_stage.region_annotations = [
        *session.analysis_stage.region_annotations,
        annotation,
    ]
    now = _utc_now()
    session.updated_at = now
    append_event(
        session,
        "annotation_changed",
        {
            "action": "added",
            "annotation_kind": "region",
            "annotation_id": annotation.id,
            "label": label,
            "start_position": start_position,
            "end_position": end_position,
            "color_hex": normalized_color,
            "note": trimmed_note,
        },
    )
    return True, None


def update_region_annotation(
    session: AnalysisSession,
    annotation_id: str,
    label: str,
    start_position: int,
    end_position: int,
    alignment_length: int,
    note: str | None,
    color_hex: str,
) -> tuple[bool, str | None]:
    existing = session.analysis_stage.region_annotations
    original = next((ann for ann in existing if ann.id == annotation_id), None)
    if original is None:
        return False, "Annotation not found."
    label = label.strip()
    if not label:
        return False, "Label must not be empty."
    if not (1 <= start_position <= end_position <= alignment_length):
        return False, f"Positions must satisfy 1 ≤ start ≤ end ≤ {alignment_length}."
    trimmed_note: str | None = note.strip() if note and note.strip() else None
    if trimmed_note is not None and len(trimmed_note) > _MAX_NOTE_LEN:
        return False, f"Note must not exceed {_MAX_NOTE_LEN} characters."
    normalized_color, color_err = _normalize_color_hex(color_hex)
    if normalized_color is None:
        return False, color_err

    updated = RegionAnnotation(
        id=annotation_id,
        label=label,
        start_position=start_position,
        end_position=end_position,
        note=trimmed_note,
        color_hex=normalized_color,
    )
    session.analysis_stage.region_annotations = [
        updated if ann.id == annotation_id else ann for ann in existing
    ]
    session.updated_at = _utc_now()
    append_event(
        session,
        "annotation_changed",
        {
            "action": "updated",
            "annotation_kind": "region",
            "annotation_id": annotation_id,
            "label": label,
            "start_position": start_position,
            "end_position": end_position,
            "color_hex": normalized_color,
            "note": trimmed_note,
        },
    )
    return True, None


def delete_region_annotation(session: AnalysisSession, annotation_id: str) -> bool:
    existing = session.analysis_stage.region_annotations
    removed = next((ann for ann in existing if ann.id == annotation_id), None)
    if removed is None:
        return False
    session.analysis_stage.region_annotations = [
        ann for ann in existing if ann.id != annotation_id
    ]
    session.updated_at = _utc_now()
    append_event(
        session,
        "annotation_changed",
        {
            "action": "deleted",
            "annotation_kind": "region",
            "annotation_id": annotation_id,
            "label": removed.label,
            "start_position": removed.start_position,
            "end_position": removed.end_position,
            "color_hex": removed.color_hex,
            "note": removed.note,
        },
    )
    return True


def add_or_update_amino_acid_annotation(
    session: AnalysisSession,
    amino_acid: str,
    note: str,
) -> tuple[bool, str | None]:
    amino_acid = amino_acid.strip()
    if amino_acid not in _CANONICAL_AAS:
        return False, f"'{amino_acid}' is not a canonical amino acid."
    note = note.strip()
    if not note:
        return False, "Note must not be empty."
    if len(note) > _MAX_NOTE_LEN:
        return False, f"Note must not exceed {_MAX_NOTE_LEN} characters."

    existing = session.analysis_stage.amino_acid_annotations
    matched = next((ann for ann in existing if ann.amino_acid == amino_acid), None)

    if matched is not None:
        updated = AminoAcidAnnotation(id=matched.id, amino_acid=amino_acid, note=note)
        session.analysis_stage.amino_acid_annotations = [
            updated if ann.amino_acid == amino_acid else ann for ann in existing
        ]
        action = "updated"
        ann_id = matched.id
    else:
        new_ann = AminoAcidAnnotation(id=_new_ann_id(), amino_acid=amino_acid, note=note)
        session.analysis_stage.amino_acid_annotations = [*existing, new_ann]
        action = "added"
        ann_id = new_ann.id

    session.updated_at = _utc_now()
    append_event(
        session,
        "annotation_changed",
        {
            "action": action,
            "annotation_kind": "amino_acid",
            "annotation_id": ann_id,
            "residue_one_letter": amino_acid,
            "residue_three_letter": AMINO_ACID_THREE_LETTER.get(amino_acid, ""),
            "note": note,
        },
    )
    return True, None


def delete_amino_acid_annotation(session: AnalysisSession, annotation_id: str) -> bool:
    existing = session.analysis_stage.amino_acid_annotations
    removed = next((ann for ann in existing if ann.id == annotation_id), None)
    if removed is None:
        return False
    session.analysis_stage.amino_acid_annotations = [
        ann for ann in existing if ann.id != annotation_id
    ]
    session.updated_at = _utc_now()
    append_event(
        session,
        "annotation_changed",
        {
            "action": "deleted",
            "annotation_kind": "amino_acid",
            "annotation_id": annotation_id,
            "residue_one_letter": removed.amino_acid,
            "residue_three_letter": AMINO_ACID_THREE_LETTER.get(removed.amino_acid, ""),
            "note": removed.note,
        },
    )
    return True
