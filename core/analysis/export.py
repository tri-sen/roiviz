from __future__ import annotations

import csv
import io
import json
import re

from core.analysis_session_models import AnalysisSession
from core.constants import AMINO_ACID_THREE_LETTER


def _sanitize_fasta_name(name: str) -> str:
    name = re.sub(r"[\r\n\t\x00-\x1f\x7f]", " ", name)
    name = re.sub(r" {2,}", " ", name)
    name = name.replace("|", "/")
    return name.strip()


def build_provenance_log_json(session: AnalysisSession) -> str:
    events = [
        {"timestamp": e.timestamp, "event_type": e.event_type, "payload": e.payload}
        for e in session.provenance_log
    ]
    return json.dumps(
        {"session_id": session.id, "export_type": "provenance_log", "events": events},
        indent=2,
    )


def build_sequences_and_alignment_fasta(session: AnalysisSession) -> str:
    sid = session.id
    aligned_by_seq_id = {a.input_sequence_id: a for a in session.alignment_stage.aligned_sequences}
    lines: list[str] = []
    for seq in session.input_stage.selected_sequences:
        name = _sanitize_fasta_name(seq.name)
        lines.append(f">input|session_id={sid}|input_sequence_id={seq.id}|name={name}")
        lines.append(seq.sequence)
        aligned = aligned_by_seq_id.get(seq.id)
        if aligned is not None:
            lines.append(
                f">aligned|session_id={sid}|input_sequence_id={seq.id}"
                f"|aligned_sequence_id={aligned.id}|name={name}"
            )
            lines.append(aligned.aligned_sequence)
    return "\n".join(lines) + "\n"


def build_metric_pairwise_deltas_csv(session: AnalysisSession) -> str:
    profiles = session.analysis_stage.computed_profiles
    if profiles is None:
        return ""
    pair_label_by_id = {p.pair_id: p.pair_label for p in profiles.alignment_pairs}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "pair_id", "pair_label", "position", "abs_delta_normalized"])
    for delta in profiles.pairwise_metric_deltas:
        writer.writerow([
            delta.metric,
            delta.pair_id,
            pair_label_by_id.get(delta.pair_id, ""),
            delta.position,
            f"{delta.abs_delta_normalized:.6f}",
        ])
    return buf.getvalue()


def build_position_composition_csv(session: AnalysisSession) -> str:
    profiles = session.analysis_stage.computed_profiles
    if profiles is None:
        return ""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["position", "symbol", "residue_name", "count", "fraction"])
    for entry in profiles.position_composition:
        if entry.fraction <= 0.0:
            continue
        writer.writerow([
            entry.position, entry.symbol, entry.residue_name,
            entry.count, f"{entry.fraction:.6f}",
        ])
    return buf.getvalue()


def build_region_annotations_csv(session: AnalysisSession) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["session_id", "annotation_id", "start_position", "end_position", "label", "note", "color_hex"])
    for ann in session.analysis_stage.region_annotations:
        writer.writerow([
            session.id, ann.id, ann.start_position, ann.end_position,
            ann.label, ann.note or "", ann.color_hex,
        ])
    return buf.getvalue()


def build_amino_acid_annotations_csv(session: AnalysisSession) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["session_id", "annotation_id", "residue_one_letter", "residue_three_letter", "note"])
    for ann in sorted(session.analysis_stage.amino_acid_annotations, key=lambda a: a.amino_acid):
        writer.writerow([
            session.id, ann.id, ann.amino_acid,
            AMINO_ACID_THREE_LETTER.get(ann.amino_acid, ""),
            ann.note,
        ])
    return buf.getvalue()
