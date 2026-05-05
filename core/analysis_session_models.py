from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StageName(StrEnum):
    INPUT = "input"
    ALIGNMENT = "alignment"
    ANALYSIS = "analysis"


class SourceType(StrEnum):
    MANUAL = "MANUAL"
    FASTA_UPLOAD = "FASTA_UPLOAD"
    GENBANK_UPLOAD = "GENBANK_UPLOAD"
    NCBI_FETCH = "NCBI_FETCH"


class AlignmentStatus(StrEnum):
    NOT_RUN = "not_run"
    SUCCESS = "success"
    ERROR = "error"


class CompositionMode(StrEnum):
    STACKED_COLUMNS = "stacked_columns"
    LETTER_GAP_SYMBOLS = "letter_gap_symbols"


@dataclass
class ProteinCandidate:
    id: str
    source_id: str
    name: str
    sequence: str
    description: str | None = None
    feature_type: str | None = None
    feature_location: str | None = None


@dataclass
class InputSource:
    id: str
    source_type: SourceType
    display_label: str | None = None
    filename: str | None = None
    accession: str | None = None
    imported_at: str = ""


@dataclass
class InputSequence:
    id: str
    source_id: str
    candidate_id: str
    name: str
    sequence: str


@dataclass
class InputStage:
    sources: list[InputSource] = field(default_factory=list)
    candidates: list[ProteinCandidate] = field(default_factory=list)
    selected_sequences: list[InputSequence] = field(default_factory=list)


@dataclass
class AlignedSequence:
    id: str
    input_sequence_id: str
    name: str
    aligned_sequence: str


@dataclass
class AlignmentStage:
    status: AlignmentStatus = AlignmentStatus.NOT_RUN
    aligner: str | None = None
    mafft_mode: str = "auto"
    mafft_args: list[str] = field(default_factory=list)
    mafft_version: str | None = None
    mafft_timeout_seconds: int = 120
    mafft_exit_code: int | None = None
    mafft_stdout_snippet: str | None = None
    mafft_stderr_snippet: str | None = None
    mafft_stdout_truncated: bool = False
    mafft_stderr_truncated: bool = False
    aligned_sequences: list[AlignedSequence] = field(default_factory=list)
    alignment_length: int | None = None
    completed_at: str | None = None
    error_summary: str | None = None


@dataclass
class AlignmentPair:
    pair_id: str
    aligned_sequence_a_id: str
    aligned_sequence_b_id: str
    pair_label: str


@dataclass
class PairwiseMetricDelta:
    metric: str
    position: int
    pair_id: str
    aligned_sequence_a_id: str
    aligned_sequence_b_id: str
    residue_a: str
    residue_b: str
    gap_in_pair: bool
    abs_delta_normalized: float


@dataclass
class PositionCompositionEntry:
    position: int
    symbol: str
    residue_name: str
    count: int
    fraction: float


@dataclass
class ComputedProfiles:
    created_at: str
    alignment_length: int
    aligned_sequence_ids: list[str] = field(default_factory=list)
    alignment_pairs: list[AlignmentPair] = field(default_factory=list)
    pairwise_metric_deltas: list[PairwiseMetricDelta] = field(default_factory=list)
    position_composition: list[PositionCompositionEntry] = field(default_factory=list)


@dataclass
class RegionAnnotation:
    id: str
    label: str
    start_position: int
    end_position: int
    note: str | None
    color_hex: str


@dataclass
class AminoAcidAnnotation:
    id: str
    amino_acid: str
    note: str


@dataclass
class UiSettings:
    composition_display_mode: CompositionMode = CompositionMode.STACKED_COLUMNS
    show_explanations: bool = True
    amino_acid_palette_key: str = "zappo_physicochemical"


@dataclass
class AnalysisStage:
    completed_at: str | None = None
    computed_profiles: ComputedProfiles | None = None
    region_annotations: list[RegionAnnotation] = field(default_factory=list)
    amino_acid_annotations: list[AminoAcidAnnotation] = field(default_factory=list)


@dataclass
class ProvenanceEvent:
    timestamp: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisSession:
    id: str
    created_at: str
    updated_at: str
    ui_settings: UiSettings = field(default_factory=UiSettings)
    input_stage: InputStage = field(default_factory=InputStage)
    alignment_stage: AlignmentStage = field(default_factory=AlignmentStage)
    analysis_stage: AnalysisStage = field(default_factory=AnalysisStage)
    provenance_log: list[ProvenanceEvent] = field(default_factory=list)
