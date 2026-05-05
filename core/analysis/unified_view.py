from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.analysis.composition_chart import (
    build_composition_letter_symbols,
    build_composition_stacked_columns,
)
from core.analysis_session_models import (
    AminoAcidAnnotation,
    ComputedProfiles,
    PairwiseMetricDelta,
    RegionAnnotation,
)
from core.constants import (
    AMINO_ACID_THREE_LETTER,
    GAP_CHAR,
    NORMALIZED_HYDROPATHY,
    NORMALIZED_POLAR_REQUIREMENT,
    PALETTES,
    STANDARD_AMINO_ACIDS,
)

ROW_HYDROPATHY = 1
ROW_POLAR_REQUIREMENT = 2
ROW_ANNOTATIONS = 3
ROW_COMPOSITION = 4


_NEUTRAL_BORDER = "#AAAAAA"


def _hex_to_rgba(hex_color: str, alpha: float = 0.40) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"

_AA_BORDER_COLOR: dict[str, str] = {
    aa: PALETTES["default"][i % len(PALETTES["default"])]
    for i, aa in enumerate(STANDARD_AMINO_ACIDS)
}
_CANONICAL_AA_SET: frozenset[str] = frozenset(STANDARD_AMINO_ACIDS)


# ── index builders ────────────────────────────────────────────────────────────


def _build_delta_index(
    profiles: ComputedProfiles,
) -> dict[tuple[str, int, str], PairwiseMetricDelta]:
    """Build (metric, position, pair_id) → PairwiseMetricDelta lookup."""
    return {
        (d.metric, d.position, d.pair_id): d
        for d in profiles.pairwise_metric_deltas
    }


def _build_comp_index(profiles: ComputedProfiles) -> dict[int, dict[str, float]]:
    """Build position → {symbol → fraction} lookup."""
    comp: dict[int, dict[str, float]] = {}
    for entry in profiles.position_composition:
        comp.setdefault(entry.position, {})[entry.symbol] = entry.fraction
    return comp


# ── hover helpers ─────────────────────────────────────────────────────────────


def _truncate_note(note: str) -> str:
    note = note.strip()
    return note if len(note) <= 120 else note[:117] + "..."


def _composition_border_color(composition: dict[str, float]) -> str:
    aa_items = [(aa, frac) for aa, frac in composition.items() if aa in _CANONICAL_AA_SET and frac > 0]
    if not aa_items:
        return _NEUTRAL_BORDER
    max_frac = max(frac for _, frac in aa_items)
    top = [aa for aa, frac in aa_items if frac == max_frac]
    if len(top) == 1:
        return _AA_BORDER_COLOR.get(top[0], _NEUTRAL_BORDER)
    return _NEUTRAL_BORDER


def _sym_name(sym: str) -> str:
    if sym == GAP_CHAR:
        return "Gap"
    return AMINO_ACID_THREE_LETTER.get(sym, sym)


def _dominant_symbol_line(composition: dict[str, float]) -> str:
    sorted_items = sorted(
        ((sym, frac) for sym, frac in composition.items() if frac > 0),
        key=lambda x: x[1],
        reverse=True,
    )
    if not sorted_items:
        return "None"
    top_sym, top_frac = sorted_items[0]
    tied = [sym for sym, frac in sorted_items if frac == top_frac]
    if len(tied) >= 2:
        names = [f"{s} {_sym_name(s)}" for s in tied[:2]]
        return f"Tie between {' and '.join(names)} ({top_frac * 100:.1f}% each)"
    if top_sym == GAP_CHAR:
        non_gap = [(s, f) for s, f in sorted_items if s != GAP_CHAR]
        if non_gap:
            sec_sym, sec_frac = non_gap[0]
            return (
                f"- Gap ({top_frac * 100:.1f}%); "
                f"second residue: {sec_sym} {_sym_name(sec_sym)} ({sec_frac * 100:.1f}%)"
            )
        return f"- Gap ({top_frac * 100:.1f}%); second residue: None"
    return f"{top_sym} {_sym_name(top_sym)} ({top_frac * 100:.1f}%)"


def _annotation_sections_text(
    position: int,
    region_annotations: list[RegionAnnotation],
    amino_acid_annotations: list[AminoAcidAnnotation],
    composition: dict[str, float],
) -> str:
    sections: list[str] = []

    matching_regions = [a for a in region_annotations if a.start_position <= position <= a.end_position]
    if matching_regions:
        rows = ["<b>Regional annotations:</b>"]
        for ann in matching_regions:
            label_part = f"{ann.label}: {_truncate_note(ann.note)}" if ann.note else ann.label
            rows.append(f"- [{ann.start_position}-{ann.end_position}] {label_part}")
        sections.append("<br>".join(rows))

    ann_by_aa = {ann.amino_acid: ann for ann in amino_acid_annotations}
    matching_aas = [
        (aa, ann_by_aa[aa])
        for aa in STANDARD_AMINO_ACIDS
        if aa in ann_by_aa and composition.get(aa, 0.0) > 0
    ]
    if matching_aas:
        rows = ["<b>Amino-acid annotations:</b>"]
        for aa, ann in matching_aas:
            three = AMINO_ACID_THREE_LETTER.get(aa, aa)
            rows.append(f"- [{three}/{aa}] {_truncate_note(ann.note)}")
        sections.append("<br>".join(rows))

    return "<br><br>".join(sections)


def _build_annotation_pos_hover(
    position: int,
    region_annotations: list[RegionAnnotation],
    amino_acid_annotations: list[AminoAcidAnnotation],
    composition: dict[str, float],
) -> str:
    text = _annotation_sections_text(position, region_annotations, amino_acid_annotations, composition)
    return text if text else f"Position {position}: no annotations"


def _build_composition_hover_text(
    position: int,
    composition: dict[str, float],
    n_seqs: int,
    region_annotations: list[RegionAnnotation],
    amino_acid_annotations: list[AminoAcidAnnotation],
) -> str:
    sorted_items = sorted(
        ((sym, frac) for sym, frac in composition.items() if frac > 0),
        key=lambda x: x[1],
        reverse=True,
    )
    comp_rows = [
        f"{sym} {_sym_name(sym)}: {round(frac * n_seqs)} / {n_seqs} ({frac * 100:.1f}%)"
        for sym, frac in sorted_items
    ]
    sections = [
        f"<b>Position {position} — Residue/gap composition</b>",
        f"Dominant symbol: {_dominant_symbol_line(composition)}",
        "Full composition:<br>" + "<br>".join(comp_rows),
    ]
    ann_text = _annotation_sections_text(position, region_annotations, amino_acid_annotations, composition)
    if ann_text:
        sections.append(ann_text)
    return "<br><br>".join(sections)


# ── metric traces ─────────────────────────────────────────────────────────────


def _build_pairwise_hover_texts(
    profiles: ComputedProfiles,
    delta_index: dict[tuple[str, int, str], PairwiseMetricDelta],
    positions: list[int],
    region_annotations: list[RegionAnnotation],
    amino_acid_annotations: list[AminoAcidAnnotation],
    comp_index: dict[int, dict[str, float]],
) -> tuple[list[str], list[str]]:
    """Build per-position hover text for hydropathy and polar requirement rows."""
    h_texts: list[str] = []
    pr_texts: list[str] = []
    n_pairs = len(profiles.alignment_pairs)

    for pos in positions:
        composition = comp_index.get(pos, {})

        gap_count = sum(
            1
            for pair in profiles.alignment_pairs
            if (d := delta_index.get(("hydropathy", pos, pair.pair_id))) and d.gap_in_pair
        )

        h_rows: list[str] = []
        pr_rows: list[str] = []
        for pair in profiles.alignment_pairs:
            h_d = delta_index.get(("hydropathy", pos, pair.pair_id))
            pr_d = delta_index.get(("polar_requirement", pos, pair.pair_id))

            if h_d is None:
                h_rows.append(f"{pair.pair_label}: n/a")
                pr_rows.append(f"{pair.pair_label}: n/a")
                continue

            if h_d.gap_in_pair:
                h_rows.append(f"{pair.pair_label}: gap present = 0.00")
                pr_rows.append(f"{pair.pair_label}: gap present = 0.00")
            else:
                res_a, res_b = h_d.residue_a, h_d.residue_b
                h_a = NORMALIZED_HYDROPATHY.get(res_a, 0.0)
                h_b = NORMALIZED_HYDROPATHY.get(res_b, 0.0)
                pr_a = NORMALIZED_POLAR_REQUIREMENT.get(res_a, 0.0)
                pr_b = NORMALIZED_POLAR_REQUIREMENT.get(res_b, 0.0)
                h_rows.append(f"{pair.pair_label}: |{h_a:.2f} - {h_b:.2f}| = {h_d.abs_delta_normalized:.2f}")
                pr_val = pr_d.abs_delta_normalized if pr_d else 0.0
                pr_rows.append(f"{pair.pair_label}: |{pr_a:.2f} - {pr_b:.2f}| = {pr_val:.2f}")

        ann_text = _annotation_sections_text(pos, region_annotations, amino_acid_annotations, composition)

        h_sections = [
            f"<b>Position {pos} — Hydropathy pairwise |Δ|</b>",
            f"Gap pairs: {gap_count} / {n_pairs}",
            "Pairwise |ΔH|<br>" + "<br>".join(h_rows),
        ]
        if ann_text:
            h_sections.append(ann_text)
        h_texts.append("<br><br>".join(h_sections))

        pr_sections = [
            f"<b>Position {pos} — Polar requirement pairwise |Δ|</b>",
            f"Gap pairs: {gap_count} / {n_pairs}",
            "Pairwise |ΔPR|<br>" + "<br>".join(pr_rows),
        ]
        if ann_text:
            pr_sections.append(ann_text)
        pr_texts.append("<br><br>".join(pr_sections))

    return h_texts, pr_texts


def _add_pairwise_metric_traces(
    fig: go.Figure,
    profiles: ComputedProfiles,
    delta_index: dict[tuple[str, int, str], PairwiseMetricDelta],
    positions: list[int],
    colors: tuple[str, ...],
    h_hover_texts: list[str],
    pr_hover_texts: list[str],
    border_colors: list[str],
) -> None:
    for i, pair in enumerate(profiles.alignment_pairs):
        color = colors[i % len(colors)]

        h_values = [
            (delta_index.get(("hydropathy", pos, pair.pair_id)) or type("", (), {"abs_delta_normalized": 0.0})()).abs_delta_normalized
            for pos in positions
        ]
        pr_values = [
            (delta_index.get(("polar_requirement", pos, pair.pair_id)) or type("", (), {"abs_delta_normalized": 0.0})()).abs_delta_normalized
            for pos in positions
        ]

        fig.add_trace(
            go.Scatter(
                x=positions,
                y=h_values,
                mode="lines",
                name=pair.pair_label,
                line=dict(color=color, width=1.5),
                showlegend=True,
                legendgroup=pair.pair_id,
                hoverinfo="skip",
            ),
            row=ROW_HYDROPATHY,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=positions,
                y=pr_values,
                mode="lines",
                name=pair.pair_label,
                line=dict(color=color, width=1.5),
                showlegend=False,
                legendgroup=pair.pair_id,
                hoverinfo="skip",
            ),
            row=ROW_POLAR_REQUIREMENT,
            col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=positions,
            y=[0.5] * len(positions),
            mode="markers",
            marker=dict(opacity=0, size=8, color="rgba(0,0,0,0)"),
            hovertext=h_hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
            hoverlabel=dict(bordercolor=border_colors),
            showlegend=False,
            name="",
        ),
        row=ROW_HYDROPATHY,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=positions,
            y=[0.5] * len(positions),
            mode="markers",
            marker=dict(opacity=0, size=8, color="rgba(0,0,0,0)"),
            hovertext=pr_hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
            hoverlabel=dict(bordercolor=border_colors),
            showlegend=False,
            name="",
        ),
        row=ROW_POLAR_REQUIREMENT,
        col=1,
    )


# ── annotation row ────────────────────────────────────────────────────────────


def _truncate_annotation_label(label: str, max_chars: int = 24) -> str:
    import re as _re
    cleaned = _re.sub(r"\s+", " ", label).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "..."


def _annotation_label_font_size(n_lanes: int) -> int:
    if n_lanes <= 1:
        return 11
    if n_lanes == 2:
        return 10
    if n_lanes == 3:
        return 9
    return 8


def _assign_annotation_lanes(annotations: list[RegionAnnotation]) -> list[int]:
    if not annotations:
        return []
    sorted_idx = sorted(range(len(annotations)), key=lambda i: annotations[i].start_position)
    lane_ends: list[int] = []
    result = [0] * len(annotations)
    for idx in sorted_idx:
        ann = annotations[idx]
        assigned = next(
            (li for li, end in enumerate(lane_ends) if end < ann.start_position),
            None,
        )
        if assigned is None:
            assigned = len(lane_ends)
            lane_ends.append(ann.end_position)
        else:
            lane_ends[assigned] = ann.end_position
        result[idx] = assigned
    return result


def _add_annotation_row(
    fig: go.Figure,
    positions: list[int],
    alignment_length: int,
    region_annotations: list[RegionAnnotation],
    carrier_hover_texts: list[str],
    border_colors: list[str],
) -> None:
    if not region_annotations:
        fig.add_trace(
            go.Scatter(
                x=[alignment_length // 2 + 1],
                y=[0.5],
                mode="text",
                text=["No region annotations"],
                textfont=dict(color="gray", size=11),
                hoverinfo="skip",
                showlegend=False,
                name="",
            ),
            row=ROW_ANNOTATIONS,
            col=1,
        )
    else:
        lane_assignments = _assign_annotation_lanes(region_annotations)
        n_lanes = max(lane_assignments) + 1
        lane_h = 1.0 / n_lanes
        bar_pad = lane_h * 0.225
        label_font_size = _annotation_label_font_size(n_lanes)

        for i, ann in enumerate(region_annotations):
            lane = lane_assignments[i]
            y0 = lane * lane_h + bar_pad
            y1 = (lane + 1) * lane_h - bar_pad

            fig.add_shape(
                type="rect",
                x0=ann.start_position - 0.5,
                x1=ann.end_position + 0.5,
                y0=y0,
                y1=y1,
                fillcolor=_hex_to_rgba(ann.color_hex, 0.40),
                line=dict(width=0),
                row=ROW_ANNOTATIONS,
                col=1,
            )
            fig.add_annotation(
                x=(ann.start_position + ann.end_position) / 2,
                y=(y0 + y1) / 2,
                text=_truncate_annotation_label(ann.label),
                showarrow=False,
                xanchor="center",
                yanchor="middle",
                align="center",
                bgcolor="rgba(0, 0, 0, 0.65)",
                bordercolor="rgba(0, 0, 0, 0)",
                borderpad=2,
                font=dict(color="white", size=label_font_size),
                row=ROW_ANNOTATIONS,
                col=1,
            )

    fig.add_trace(
        go.Scatter(
            x=positions,
            y=[0.5] * len(positions),
            mode="markers",
            marker=dict(opacity=0, size=8, color="rgba(0,0,0,0)"),
            hovertext=carrier_hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
            hoverlabel=dict(bordercolor=border_colors),
            showlegend=False,
            name="",
        ),
        row=ROW_ANNOTATIONS,
        col=1,
    )


# ── main builder ──────────────────────────────────────────────────────────────


def build_unified_analysis_figure(
    profiles: ComputedProfiles,
    composition_mode: str = "stacked",
    region_annotations: list[RegionAnnotation] | None = None,
    amino_acid_annotations: list[AminoAcidAnnotation] | None = None,
    aligned_sequences: list | None = None,
    palette: dict[str, str] | None = None,
) -> go.Figure:
    if region_annotations is None:
        region_annotations = []
    if amino_acid_annotations is None:
        amino_acid_annotations = []

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.20, 0.20, 0.30, 0.25],
        subplot_titles=("Position-specific pairwise Hydropathy difference", "Position-specific pairwise Polar requirement difference", "", "Position-specific amino acid composition"),
        vertical_spacing=0.08,
    )

    alignment_length = profiles.alignment_length
    positions = list(range(1, alignment_length + 1))
    n_seqs = len(profiles.aligned_sequence_ids)

    delta_index = _build_delta_index(profiles)
    comp_index = _build_comp_index(profiles)

    colors = PALETTES.get("default", ())

    border_colors = [
        _composition_border_color(comp_index.get(pos, {})) for pos in positions
    ]

    h_hover_texts, pr_hover_texts = _build_pairwise_hover_texts(
        profiles, delta_index, positions, region_annotations, amino_acid_annotations, comp_index
    )
    _add_pairwise_metric_traces(
        fig, profiles, delta_index, positions, colors, h_hover_texts, pr_hover_texts, border_colors
    )

    ann_carrier_texts = [
        _build_annotation_pos_hover(pos, region_annotations, amino_acid_annotations, comp_index.get(pos, {}))
        for pos in positions
    ]
    _add_annotation_row(fig, positions, alignment_length, region_annotations, ann_carrier_texts, border_colors)

    composition_hover_texts = [
        _build_composition_hover_text(pos, comp_index.get(pos, {}), n_seqs, region_annotations, amino_acid_annotations)
        for pos in positions
    ]

    if composition_mode == "symbols":
        composition_fig = build_composition_letter_symbols(profiles, palette=palette)
    else:
        composition_fig = build_composition_stacked_columns(profiles, palette=palette)

    for trace in composition_fig.data:
        trace.update(hoverinfo="skip", hovertemplate=None)
    for trace in composition_fig.data:
        fig.add_trace(trace, row=ROW_COMPOSITION, col=1)

    fig.add_trace(
        go.Scatter(
            x=positions,
            y=[0.5] * len(positions),
            mode="markers",
            marker=dict(opacity=0, size=8, color="rgba(0,0,0,0)"),
            hovertext=composition_hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
            hoverlabel=dict(bordercolor=border_colors),
            showlegend=False,
            name="",
        ),
        row=ROW_COMPOSITION,
        col=1,
    )

    layout_kwargs: dict = {
        "height": 900,
        "title_text": "Alignment Analysis",
        "hovermode": "closest",
        "hoverdistance": -1,
        "showlegend": True,
        "margin": dict(l=60, r=20, t=80, b=50),
    }
    if composition_mode == "stacked":
        layout_kwargs["barmode"] = "stack"

    fig.update_layout(**layout_kwargs)

    _sep = dict(line_dash="solid", line_width=0.5, line_color="rgba(200, 200, 200, 0.3)", opacity=0.3)
    fig.add_hline(y=1.0, row=ROW_POLAR_REQUIREMENT, col=1, **_sep)
    fig.add_hline(y=1.0, row=ROW_COMPOSITION, col=1, **_sep)

    x_min = 0.5
    x_max = alignment_length + 0.5

    for row in range(1, 5):
        fig.update_xaxes(
            range=[x_min, x_max],
            minallowed=x_min,
            maxallowed=x_max,
            autorange=False,
            tickmode="linear",
            tick0=1,
            dtick=1,
            row=row,
            col=1,
        )

    _spike_kwargs = dict(showspikes=True, spikemode="across", spikesnap="data", spikedash="dash")
    for row in [ROW_HYDROPATHY, ROW_POLAR_REQUIREMENT, ROW_ANNOTATIONS, ROW_COMPOSITION]:
        fig.update_xaxes(**_spike_kwargs, row=row, col=1)

    fig.update_xaxes(showticklabels=True, row=ROW_HYDROPATHY, col=1)
    fig.update_xaxes(showticklabels=True, row=ROW_POLAR_REQUIREMENT, col=1)
    fig.update_xaxes(showticklabels=True, row=ROW_ANNOTATIONS, col=1)
    fig.update_xaxes(title_text="Aligned position", showticklabels=True, row=ROW_COMPOSITION, col=1)

    fig.update_yaxes(
        range=[0, 1], fixedrange=True, tickmode="linear", tick0=0, dtick=0.2,
        title_text="|ΔH| (0-1)", row=ROW_HYDROPATHY, col=1,
    )

    fig.update_yaxes(
        range=[0, 1], fixedrange=True, tickmode="linear", tick0=0, dtick=0.2,
        title_text="|ΔPR| (0-1)", row=ROW_POLAR_REQUIREMENT, col=1,
    )
    fig.update_yaxes(
        range=[0, 1], fixedrange=True,
        showticklabels=False, showgrid=False, title_text="",
        row=ROW_ANNOTATIONS, col=1,
    )
    fig.update_yaxes(
        range=[0, 1], fixedrange=True, tickmode="linear", tick0=0, dtick=0.2,
        tickformat=".0%", title_text="Composition (%)", row=ROW_COMPOSITION, col=1,
    )

    return fig
