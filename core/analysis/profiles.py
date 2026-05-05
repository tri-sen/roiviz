from __future__ import annotations

from datetime import UTC, datetime
from itertools import combinations

from core.analysis_session_models import (
    AlignmentPair,
    AlignmentStatus,
    AnalysisSession,
    ComputedProfiles,
    PairwiseMetricDelta,
    PositionCompositionEntry,
)
from core.constants import (
    AMINO_ACID_THREE_LETTER,
    GAP_CHAR,
    NORMALIZED_HYDROPATHY,
    NORMALIZED_POLAR_REQUIREMENT,
    STANDARD_AMINO_ACIDS,
)
from core.provenance_log import append_event

_ALL_SYMBOLS: list[str] = list(STANDARD_AMINO_ACIDS) + [GAP_CHAR]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def compute_profiles(session: AnalysisSession) -> tuple[bool, str | None]:
    if session.alignment_stage.status != AlignmentStatus.SUCCESS:
        return False, "Alignment step is not locked. Complete Step 2 first."

    aligned_seqs = session.alignment_stage.aligned_sequences
    alignment_length = session.alignment_stage.alignment_length

    if not aligned_seqs:
        return False, "No aligned sequences found."
    if not alignment_length:
        return False, "Alignment length is zero."

    # Pair IDs use alnseq_ IDs sorted lexicographically, separated by "__".
    pairs: list[AlignmentPair] = []
    for a, b in combinations(aligned_seqs, 2):
        id_a, id_b = (a.id, b.id) if a.id <= b.id else (b.id, a.id)
        pairs.append(
            AlignmentPair(
                pair_id=f"pair_{id_a}__{id_b}",
                aligned_sequence_a_id=id_a,
                aligned_sequence_b_id=id_b,
                pair_label=f"{a.name} / {b.name}" if id_a == a.id else f"{b.name} / {a.name}",
            )
        )

    # Index aligned sequences by alnseq_ ID for O(1) position access.
    seq_str_by_id: dict[str, str] = {a.id: a.aligned_sequence for a in aligned_seqs}

    metric_deltas: list[PairwiseMetricDelta] = []
    composition_entries: list[PositionCompositionEntry] = []

    for pos in range(alignment_length):
        aligned_pos = pos + 1

        # Pairwise metric deltas (both metrics per pair per position).
        for pair in pairs:
            res_a = seq_str_by_id[pair.aligned_sequence_a_id][pos]
            res_b = seq_str_by_id[pair.aligned_sequence_b_id][pos]
            is_gap = res_a == GAP_CHAR or res_b == GAP_CHAR

            if is_gap:
                h_delta = 0.0
                pr_delta = 0.0
            else:
                h_delta = abs(NORMALIZED_HYDROPATHY[res_a] - NORMALIZED_HYDROPATHY[res_b])
                pr_delta = abs(
                    NORMALIZED_POLAR_REQUIREMENT[res_a] - NORMALIZED_POLAR_REQUIREMENT[res_b]
                )

            metric_deltas.append(PairwiseMetricDelta(
                metric="hydropathy",
                position=aligned_pos,
                pair_id=pair.pair_id,
                aligned_sequence_a_id=pair.aligned_sequence_a_id,
                aligned_sequence_b_id=pair.aligned_sequence_b_id,
                residue_a=res_a,
                residue_b=res_b,
                gap_in_pair=is_gap,
                abs_delta_normalized=h_delta,
            ))
            metric_deltas.append(PairwiseMetricDelta(
                metric="polar_requirement",
                position=aligned_pos,
                pair_id=pair.pair_id,
                aligned_sequence_a_id=pair.aligned_sequence_a_id,
                aligned_sequence_b_id=pair.aligned_sequence_b_id,
                residue_a=res_a,
                residue_b=res_b,
                gap_in_pair=is_gap,
                abs_delta_normalized=pr_delta,
            ))

        # Composition: all 20 AAs + gap, including zero counts per SPEC §8.6.
        symbol_counts: dict[str, int] = {}
        for a in aligned_seqs:
            sym = seq_str_by_id[a.id][pos]
            symbol_counts[sym] = symbol_counts.get(sym, 0) + 1
        total = len(aligned_seqs)

        for sym in _ALL_SYMBOLS:
            count = symbol_counts.get(sym, 0)
            if sym == GAP_CHAR:
                res_name = "Gap"
            else:
                res_name = AMINO_ACID_THREE_LETTER.get(sym, sym)
            composition_entries.append(PositionCompositionEntry(
                position=aligned_pos,
                symbol=sym,
                residue_name=res_name,
                count=count,
                fraction=count / total,
            ))

    now = _utc_now()
    session.analysis_stage.computed_profiles = ComputedProfiles(
        created_at=now,
        alignment_length=alignment_length,
        aligned_sequence_ids=[a.id for a in aligned_seqs],
        alignment_pairs=pairs,
        pairwise_metric_deltas=metric_deltas,
        position_composition=composition_entries,
    )
    session.analysis_stage.completed_at = now
    session.updated_at = now

    append_event(session, "analysis_computation", {
        "status": "succeeded",
        "aligned_sequence_count": len(aligned_seqs),
        "alignment_length": alignment_length,
        "pair_count": len(pairs),
        "metrics": ["hydropathy", "polar_requirement", "composition"],
    })

    return True, None


def clear_analysis_profiles(session: AnalysisSession) -> None:
    session.analysis_stage.computed_profiles = None
    session.analysis_stage.region_annotations = []
    session.analysis_stage.amino_acid_annotations = []
    session.updated_at = _utc_now()
    append_event(session, "downstream_state_cleared", {
        "reason": "analysis_recomputed",
        "cleared_alignment": False,
        "cleared_analysis": True,
        "cleared_annotations": True,
    })
