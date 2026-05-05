from __future__ import annotations

import dataclasses
import json
import re
from enum import Enum

from core.analysis_session_models import (
    AlignedSequence,
    AlignmentPair,
    AlignmentStage,
    AlignmentStatus,
    AminoAcidAnnotation,
    AnalysisSession,
    AnalysisStage,
    CompositionMode,
    ComputedProfiles,
    InputSequence,
    InputSource,
    InputStage,
    PairwiseMetricDelta,
    PositionCompositionEntry,
    ProteinCandidate,
    ProvenanceEvent,
    RegionAnnotation,
    SourceType,
    UiSettings,
)
from core.constants import (
    AMINO_ACID_COLOR_PALETTES,
    DEFAULT_AMINO_ACID_COLOR_PALETTE,
    STANDARD_AMINO_ACIDS,
)

_ANN_ID_RE = re.compile(r"^ann_[0-9a-f]{12}$")
_COLOR_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_CANONICAL_AAS: frozenset[str] = frozenset(STANDARD_AMINO_ACIDS)
_REGION_ANN_FIELDS = {"id", "label", "start_position", "end_position", "note", "color_hex"}
_AA_ANN_FIELDS = {"id", "amino_acid", "note"}
_MAX_NOTE_LEN = 500


class _EnumEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


# ── serialization ─────────────────────────────────────────────────────────────


def session_to_dict(session: AnalysisSession) -> dict:
    raw = dataclasses.asdict(session)
    return json.loads(json.dumps(raw, cls=_EnumEncoder))


def export_session_to_json(session: AnalysisSession) -> str | None:
    try:
        if not session.id or not session.created_at:
            return None
        data = session_to_dict(session)
        return json.dumps(data, indent=2)
    except Exception:
        return None


# ── deserialization ───────────────────────────────────────────────────────────


def _parse_protein_candidate(d: dict) -> ProteinCandidate:
    return ProteinCandidate(
        id=str(d["id"]),
        source_id=str(d["source_id"]),
        name=str(d["name"]),
        sequence=str(d["sequence"]),
        description=d.get("description"),
        feature_type=d.get("feature_type"),
        feature_location=d.get("feature_location"),
    )


def _parse_input_source(d: dict) -> InputSource:
    return InputSource(
        id=str(d["id"]),
        source_type=SourceType(d["source_type"]),
        display_label=d.get("display_label"),
        filename=d.get("filename"),
        accession=d.get("accession"),
        imported_at=str(d["imported_at"]),
    )


def _parse_input_sequence(d: dict) -> InputSequence:
    return InputSequence(
        id=str(d["id"]),
        source_id=str(d["source_id"]),
        candidate_id=str(d["candidate_id"]),
        name=str(d["name"]),
        sequence=str(d["sequence"]),
    )


def _parse_input_stage(d: dict) -> InputStage:
    return InputStage(
        sources=[_parse_input_source(s) for s in d.get("sources", [])],
        candidates=[_parse_protein_candidate(c) for c in d.get("candidates", [])],
        selected_sequences=[_parse_input_sequence(s) for s in d.get("selected_sequences", [])],
    )


def _parse_aligned_sequence(d: dict) -> AlignedSequence:
    return AlignedSequence(
        id=str(d["id"]),
        input_sequence_id=str(d["input_sequence_id"]),
        name=str(d["name"]),
        aligned_sequence=str(d["aligned_sequence"]),
    )


def _parse_alignment_stage(d: dict) -> AlignmentStage:
    return AlignmentStage(
        status=AlignmentStatus(d["status"]),
        aligner=d.get("aligner"),
        mafft_mode=str(d.get("mafft_mode", "auto")),
        mafft_args=list(d.get("mafft_args", [])),
        mafft_version=d.get("mafft_version"),
        mafft_timeout_seconds=int(d.get("mafft_timeout_seconds", 120)),
        mafft_exit_code=d.get("mafft_exit_code"),
        mafft_stdout_snippet=d.get("mafft_stdout_snippet"),
        mafft_stderr_snippet=d.get("mafft_stderr_snippet"),
        mafft_stdout_truncated=bool(d.get("mafft_stdout_truncated", False)),
        mafft_stderr_truncated=bool(d.get("mafft_stderr_truncated", False)),
        aligned_sequences=[_parse_aligned_sequence(s) for s in d.get("aligned_sequences", [])],
        alignment_length=d.get("alignment_length"),
        completed_at=d.get("completed_at"),
        error_summary=d.get("error_summary"),
    )


def _parse_alignment_pair(d: dict) -> AlignmentPair:
    return AlignmentPair(
        pair_id=str(d["pair_id"]),
        aligned_sequence_a_id=str(d["aligned_sequence_a_id"]),
        aligned_sequence_b_id=str(d["aligned_sequence_b_id"]),
        pair_label=str(d["pair_label"]),
    )


def _parse_pairwise_metric_delta(d: dict) -> PairwiseMetricDelta:
    return PairwiseMetricDelta(
        metric=str(d["metric"]),
        position=int(d["position"]),
        pair_id=str(d["pair_id"]),
        aligned_sequence_a_id=str(d["aligned_sequence_a_id"]),
        aligned_sequence_b_id=str(d["aligned_sequence_b_id"]),
        residue_a=str(d["residue_a"]),
        residue_b=str(d["residue_b"]),
        gap_in_pair=bool(d["gap_in_pair"]),
        abs_delta_normalized=float(d["abs_delta_normalized"]),
    )


def _parse_position_composition_entry(d: dict) -> PositionCompositionEntry:
    return PositionCompositionEntry(
        position=int(d["position"]),
        symbol=str(d["symbol"]),
        residue_name=str(d["residue_name"]),
        count=int(d["count"]),
        fraction=float(d["fraction"]),
    )


def _parse_computed_profiles(d: dict) -> ComputedProfiles:
    return ComputedProfiles(
        created_at=str(d["created_at"]),
        alignment_length=int(d["alignment_length"]),
        aligned_sequence_ids=list(d.get("aligned_sequence_ids", [])),
        alignment_pairs=[_parse_alignment_pair(p) for p in d.get("alignment_pairs", [])],
        pairwise_metric_deltas=[
            _parse_pairwise_metric_delta(e) for e in d.get("pairwise_metric_deltas", [])
        ],
        position_composition=[
            _parse_position_composition_entry(e) for e in d.get("position_composition", [])
        ],
    )


def _parse_region_annotation(d: dict, alignment_length: int) -> RegionAnnotation:
    extra = set(d.keys()) - _REGION_ANN_FIELDS
    if extra:
        raise ValueError(
            f"Unknown field(s) in region annotation: {', '.join(sorted(extra))}"
        )
    missing = _REGION_ANN_FIELDS - set(d.keys())
    if missing:
        raise ValueError(
            f"Missing field(s) in region annotation: {', '.join(sorted(missing))}"
        )
    ann_id = str(d["id"])
    if not _ANN_ID_RE.match(ann_id):
        raise ValueError(
            f"Invalid annotation id '{ann_id}'. Expected ann_<12 hex chars>."
        )
    label = str(d["label"]).strip()
    if not label:
        raise ValueError(f"Region annotation label must not be empty (id: {ann_id}).")
    note = d["note"]
    if note is not None:
        note_str = str(note).strip()
        if len(note_str) > _MAX_NOTE_LEN:
            raise ValueError(
                f"Region annotation note exceeds {_MAX_NOTE_LEN} characters (id: {ann_id})."
            )
        note = note_str if note_str else None
    start = int(d["start_position"])
    end = int(d["end_position"])
    if not (1 <= start <= end <= alignment_length):
        raise ValueError(
            f"Region annotation {ann_id}: start_position={start}, end_position={end} "
            f"must satisfy 1 ≤ start ≤ end ≤ {alignment_length}."
        )
    raw_color = d["color_hex"]
    if not isinstance(raw_color, str) or not _COLOR_HEX_RE.match(raw_color):
        raise ValueError(
            f"Region annotation {ann_id}: color_hex must be a 6-digit hex color like #FF0000 "
            f"(got: {raw_color!r})."
        )
    color_hex = raw_color.upper()
    return RegionAnnotation(
        id=ann_id,
        label=label,
        start_position=start,
        end_position=end,
        note=note,
        color_hex=color_hex,
    )


def _parse_amino_acid_annotation(d: dict) -> AminoAcidAnnotation:
    extra = set(d.keys()) - _AA_ANN_FIELDS
    if extra:
        raise ValueError(
            f"Unknown field(s) in amino-acid annotation: {', '.join(sorted(extra))}"
        )
    missing = _AA_ANN_FIELDS - set(d.keys())
    if missing:
        raise ValueError(
            f"Missing field(s) in amino-acid annotation: {', '.join(sorted(missing))}"
        )
    ann_id = str(d["id"])
    if not _ANN_ID_RE.match(ann_id):
        raise ValueError(
            f"Invalid annotation id '{ann_id}'. Expected ann_<12 hex chars>."
        )
    amino_acid = str(d["amino_acid"])
    if amino_acid not in _CANONICAL_AAS:
        raise ValueError(
            f"Invalid amino_acid '{amino_acid}' in annotation {ann_id}. "
            f"Must be one of ACDEFGHIKLMNPQRSTVWY."
        )
    note = str(d["note"]).strip()
    if not note:
        raise ValueError(f"Amino-acid annotation note must not be empty (id: {ann_id}).")
    if len(note) > _MAX_NOTE_LEN:
        raise ValueError(
            f"Amino-acid annotation note exceeds {_MAX_NOTE_LEN} characters (id: {ann_id})."
        )
    return AminoAcidAnnotation(id=ann_id, amino_acid=amino_acid, note=note)


def _parse_analysis_stage(d: dict, alignment_length: int | None) -> AnalysisStage:
    profiles_data = d.get("computed_profiles")
    profiles = _parse_computed_profiles(profiles_data) if profiles_data is not None else None

    raw_region = d.get("region_annotations", [])
    raw_aa = d.get("amino_acid_annotations", [])

    if profiles is None:
        if raw_region:
            raise ValueError(
                "region_annotations must be empty when computed_profiles is absent."
            )
        if raw_aa:
            raise ValueError(
                "amino_acid_annotations must be empty when computed_profiles is absent."
            )
        return AnalysisStage(
            completed_at=d.get("completed_at"),
            computed_profiles=None,
            region_annotations=[],
            amino_acid_annotations=[],
        )

    aln_len = alignment_length or 0
    region_annotations = [_parse_region_annotation(r, aln_len) for r in raw_region]
    amino_acid_annotations = [_parse_amino_acid_annotation(a) for a in raw_aa]
    return AnalysisStage(
        completed_at=d.get("completed_at"),
        computed_profiles=profiles,
        region_annotations=region_annotations,
        amino_acid_annotations=amino_acid_annotations,
    )


def _parse_ui_settings(d: dict) -> UiSettings:
    raw_palette = d.get("amino_acid_palette_key", DEFAULT_AMINO_ACID_COLOR_PALETTE)
    palette_key = raw_palette if raw_palette in AMINO_ACID_COLOR_PALETTES else DEFAULT_AMINO_ACID_COLOR_PALETTE
    return UiSettings(
        composition_display_mode=CompositionMode(
            d.get("composition_display_mode", CompositionMode.STACKED_COLUMNS)
        ),
        show_explanations=bool(d.get("show_explanations", True)),
        amino_acid_palette_key=palette_key,
    )


def _parse_provenance_event(d: dict) -> ProvenanceEvent:
    return ProvenanceEvent(
        timestamp=str(d["timestamp"]),
        event_type=str(d["event_type"]),
        payload=dict(d.get("payload", {})),
    )


def _parse_session(data: dict) -> AnalysisSession:
    alignment_stage = _parse_alignment_stage(data.get("alignment_stage", {}))
    analysis_stage = _parse_analysis_stage(
        data.get("analysis_stage", {}),
        alignment_stage.alignment_length,
    )
    return AnalysisSession(
        id=str(data["id"]),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        ui_settings=_parse_ui_settings(data.get("ui_settings", {})),
        input_stage=_parse_input_stage(data.get("input_stage", {})),
        alignment_stage=alignment_stage,
        analysis_stage=analysis_stage,
        provenance_log=[_parse_provenance_event(e) for e in data.get("provenance_log", [])],
    )


def session_from_dict(data: dict) -> AnalysisSession | None:
    try:
        session = _parse_session(data)
    except (KeyError, ValueError, TypeError, AttributeError):
        return None
    if not session.id or not session.created_at:
        return None
    return session


def import_session_from_json(json_string: str) -> AnalysisSession | None:
    try:
        data = json.loads(json_string)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return session_from_dict(data)
