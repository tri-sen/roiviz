# pages/3_visualization.py
from __future__ import annotations

import uuid
from uuid import uuid4

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core.annotations import (
    AminoAcidNote,
    RegionalAnnotation,
    build_aa_note_block,
    lane_assign,
    normalize_aa_key,
)
from core.export_bundle import build_export_zip_bytes
from core.pipeline import PipelineError, compute_profiles
from core.run_factory import create_new_run
from core.run_log import run_log
from ui.sidebar import render_sidebar


AA20 = list("ACDEFGHIKLMNPQRSTVWY")
GAP = "-"


def _pair_label(pair_key: str) -> str:
    a, b = pair_key.split("__vs__", 1)
    return f"{a}–{b}"


def _cap_list(items: list[str], limit: int = 12) -> str:
    if not items:
        return "-"
    if len(items) <= limit:
        return ", ".join(items)
    head = ", ".join(items[:limit])
    return f"{head}, … (+{len(items) - limit})"


def apply_top_legend(fig: go.Figure) -> None:
    fig.update_layout(
        legend=dict(
            orientation="h",
            x=0.0,
            xanchor="left",
            y=1.18,
            yanchor="bottom",
            traceorder="normal",
        ),
        margin=dict(l=60, r=30, t=95, b=60),
    )


def _truncate_label(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if max_chars <= 0:
        return ""
    if len(t) <= max_chars:
        return t
    if max_chars <= 2:
        return ".."
    return t[: max_chars - 2] + ".."


def _regions_covering_position(regs: list[RegionalAnnotation], pos: int) -> list[RegionalAnnotation]:
    return [r for r in regs if r.start <= pos <= r.end]


def _format_region_hover_block(regs: list[RegionalAnnotation]) -> str:
    if not regs:
        return "Regional annotation: —"
    regs_sorted = sorted(regs, key=lambda r: (r.start, r.end, r.text, r.ann_id))
    lines = ["Regional annotation:"]
    for r in regs_sorted:
        lines.append(f"start: {r.start}<br>end: {r.end}<br>note: {r.text}")
    return "<br>".join(lines)


def _plot_header(title: str, info_md: str, *, show_titles: bool, show_infos: bool) -> None:
    if show_titles:
        st.markdown(f"##### {title}")
    if show_infos:
        with st.expander("ℹ️ What this shows", expanded=False):
            st.markdown(info_md)


def _add_trace(fig: go.Figure, trace: go.BaseTraceType, *, row: int | None = None, col: int | None = None) -> None:
    if row is None or col is None:
        fig.add_trace(trace)
    else:
        fig.add_trace(trace, row=row, col=col)


def _apply_regional_track(
    fig: go.Figure,
    *,
    assigned: list[tuple[RegionalAnnotation, int]],
    lane_count: int,
    row: int,
    col: int,
) -> None:
    # Polygons for intervals + text labels (start | mid note | end)
    for ann, lane in assigned:
        x0 = ann.start - 0.5
        x1 = ann.end + 0.5
        y0 = float(lane)
        y1 = float(lane) + 1.0

        poly_x = [x0, x1, x1, x0, x0]
        poly_y = [y0, y0, y1, y1, y0]

        _add_trace(
            fig,
            go.Scatter(
                x=poly_x,
                y=poly_y,
                mode="lines",
                fill="toself",
                showlegend=False,
                line=dict(width=1),
                hovertemplate=(
                    f"start: {ann.start}<br>"
                    f"end: {ann.end}<br>"
                    f"note: {ann.text}"
                    "<extra></extra>"
                ),
            ),
            row=row,
            col=col,
        )

        span = max(1, ann.end - ann.start + 1)
        label_budget = max(0, span * 2 - 8)  # heuristic for fitting within the box
        mid_label = _truncate_label(ann.text, max_chars=label_budget)

        _add_trace(
            fig,
            go.Scatter(
                x=[ann.start - 0.35],
                y=[y0 + 0.5],
                mode="text",
                text=[str(ann.start)],
                textposition="middle left",
                showlegend=False,
                hoverinfo="skip",
            ),
            row=row,
            col=col,
        )

        if span >= 2:
            _add_trace(
                fig,
                go.Scatter(
                    x=[ann.end + 0.35],
                    y=[y0 + 0.5],
                    mode="text",
                    text=[str(ann.end)],
                    textposition="middle right",
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row,
                col=col,
            )

        if mid_label:
            _add_trace(
                fig,
                go.Scatter(
                    x=[(ann.start + ann.end) / 2],
                    y=[y0 + 0.5],
                    mode="text",
                    text=[mid_label],
                    textposition="middle center",
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row,
                col=col,
            )

    fig.update_yaxes(
        showticklabels=False,
        ticks="",
        showgrid=False,
        zeroline=False,
        fixedrange=True,
        title_text=None,
        row=row,
        col=col,
    )
    fig.update_yaxes(range=[0, max(1, lane_count)], row=row, col=col)


def _build_region_hover_customdata(
    *,
    positions: list[int],
    regions: list[RegionalAnnotation],
) -> list[str]:
    out: list[str] = []
    for pos in positions:
        regs_here = _regions_covering_position(regions, int(pos))
        out.append(_format_region_hover_block(regs_here))
    return out


# ---- Page ----
st.title("Step 3 — Visualization")

run = st.session_state.get("run")
if run is None:
    st.error("RunState missing. Open the main app page to initialize a run.")
    st.stop()

render_sidebar(create_new_run)

if run.alignment_result is None:
    st.warning("No alignment yet. Go to Step 2 and run MAFFT.")
    st.stop()

if run.computed_profiles is None:
    st.info("Profiles not computed yet.")
    if st.button(
        "Compute profiles",
        type="primary",
        help="Compute |Δ| profiles + composition from the alignment.",
    ):
        try:
            with st.spinner("Computing profiles..."):
                compute_profiles(run)
            st.success("Profiles computed.")
            st.rerun()
        except PipelineError as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001
            st.error(f"Unexpected error: {e}")
    st.stop()

p = run.computed_profiles
x = getattr(p, "positions_1based", None) or getattr(p, "aa_position", None)
if not isinstance(x, list) or not x:
    st.error("ComputedProfiles has no positions list (positions_1based / aa_position).")
    st.stop()

if "viz_uirevision" not in st.session_state:
    st.session_state["viz_uirevision"] = "keep"

# Precompute regional lanes once (shared by all plots)
assigned_regions = lane_assign(getattr(run, "regional_annotations", []) or [])
lane_count = 0 if not assigned_regions else (max(l for _, l in assigned_regions) + 1)
region_hover_only = _build_region_hover_customdata(positions=x, regions=getattr(run, "regional_annotations", []) or [])

# ---- Top controls (zoom + export) ----
controls = st.columns([1, 1], vertical_alignment="center")

with controls[0]:
    if st.button(
        "Reset X-Axis zoom (on all plots)",
        help="Resets zoom/pan state for all plots.",
    ):
        st.session_state["viz_uirevision"] = str(uuid.uuid4())
        st.rerun()

with controls[1]:
    with st.expander("Export (ZIP)", expanded=False):
        st.markdown(
            "- Generates a ZIP **in-memory** (no persistence) containing CSVs + FASTA + provenance.\n"
            "- The bundle is a snapshot of the **current run state**."
        )
        build_clicked = st.button("Build export bundle", type="primary")
        if build_clicked:
            run_log(run, "export_requested", {"page": "visualization", "kind": "zip_bundle"})
            try:
                with st.spinner("Building export ZIP..."):
                    zip_bytes = build_export_zip_bytes(run)
                st.success(f"Export bundle built ({len(zip_bytes):,} bytes).")
                st.download_button(
                    label="Download export ZIP",
                    data=zip_bytes,
                    file_name=f"roiviz_export_{run.run_id}.zip",
                    mime="application/zip",
                )
            except Exception as e:  # noqa: BLE001
                run_log(run, "export_failed", {"error": str(e)}, level="ERROR")
                st.error(f"Export failed: {e}")

# ---- Display density + regional track toggles ----
row = st.columns([1, 1, 1, 2], vertical_alignment="center")
with row[0]:
    show_plot_titles = st.checkbox("Show plot titles", value=True)
with row[1]:
    show_plot_infos = st.checkbox("Show 'What this shows'", value=False)
with row[2]:
    with st.popover("Regional track"):
        show_reg_plot1 = st.checkbox("Show on Plot 1", value=False)
        show_reg_plot2 = st.checkbox("Show on Plot 2", value=False)
        show_reg_plot3 = st.checkbox("Show on Plot 3", value=True)
with row[3]:
    st.caption("Use the popover to enable/disable the regional annotation track per plot.")

st.caption(
    "Plot 1/2: pairwise |Δ| + median(|Δ|) with IQR band (P25–P75), y fixed [0,1]. "
    "Plot 3: stacked AA/gap fractions + optional regional annotation track."
)

show_pairwise = st.checkbox(
    "Show pairwise |Δ| lines (can be noisy)",
    value=True,
    help="Shows one line per sequence-pair (can become visually dense).",
)
show_summary = st.checkbox(
    "Show median + IQR band (P25–P75)",
    value=True,
    help="Median(|Δ|) and IQR band across all pairwise |Δ| lines per column.",
)

# ---- Annotations UI ----
with st.expander("Annotations", expanded=False):
    aln = run.alignment_result
    aln_len = int(getattr(aln, "alignment_length", len(x)))

    st.markdown("**Regional annotations (intervals)**")
    col_ra = st.columns([1, 1, 3, 1], vertical_alignment="center")
    with col_ra[0]:
        ra_start = st.number_input("Start", min_value=1, max_value=aln_len, value=1, step=1, key="ra_start")
    with col_ra[1]:
        ra_end = st.number_input("End", min_value=1, max_value=aln_len, value=min(aln_len, 5), step=1, key="ra_end")
    with col_ra[2]:
        ra_text = st.text_input("Label", value="", key="ra_text", placeholder="e.g., active site region")
    with col_ra[3]:
        add_ra = st.button("Add", type="primary", key="ra_add")

    if add_ra:
        if not ra_text.strip():
            st.error("Regional annotation label must not be empty.")
        elif ra_start > ra_end:
            st.error("Start must be <= End.")
        else:
            ann = RegionalAnnotation(
                start=int(ra_start),
                end=int(ra_end),
                text=ra_text.strip(),
                ann_id=uuid4().hex,
                color=None,
            )
            run.regional_annotations.append(ann)
            run_log(run, "regional_annotation_added", {"start": ann.start, "end": ann.end, "text": ann.text})
            st.rerun()

    if run.regional_annotations:
        st.markdown("Existing intervals:")
        regs = sorted(run.regional_annotations, key=lambda r: (r.start, r.end, r.text, r.ann_id))
        for r in regs:
            c = st.columns([4, 1], vertical_alignment="center")
            with c[0]:
                st.write(f"[{r.start}, {r.end}] — {r.text}")
            with c[1]:
                if st.button("Delete", key=f"ra_del_{r.ann_id}"):
                    run.regional_annotations = [z for z in run.regional_annotations if z.ann_id != r.ann_id]
                    run_log(run, "regional_annotation_deleted", {"ann_id": r.ann_id})
                    st.rerun()
    else:
        st.caption("No regional annotations yet.")

    st.divider()

    st.markdown("**Amino-acid notes (hover)**")
    aa_choices = AA20 + [GAP]

    # NOTE: true "submit on Enter" without adding libraries is not reliable in Streamlit.
    # st.form_submit_button is the correct, deterministic submit path.
    with st.form(key="aa_note_form", clear_on_submit=True):
        c = st.columns([1, 4, 1], vertical_alignment="center")
        with c[0]:
            aa_sel = st.selectbox("AA", options=aa_choices, index=aa_choices.index("V") if "V" in aa_choices else 0)
        with c[1]:
            aa_note_text = st.text_input(
                "Note text",
                value="",
                placeholder="e.g., take property X into account",
            )
        with c[2]:
            submitted = st.form_submit_button("Add note")

        if submitted:
            try:
                k = normalize_aa_key(aa_sel)
            except ValueError as e:
                st.error(str(e))
            else:
                t = aa_note_text.strip()
                if not t:
                    st.error("Note text must not be empty.")
                else:
                    note = AminoAcidNote(note_id=uuid4().hex, text=t)
                    run.aa_annotations.setdefault(k, []).append(note)
                    run_log(run, "aa_note_added", {"aa": k, "note_id": note.note_id})
                    st.rerun()

    if run.aa_annotations:
        st.markdown("Existing AA notes (grouped):")
        for k in AA20 + [GAP]:
            notes = run.aa_annotations.get(k, [])
            if not notes:
                continue
            st.markdown(f"**{k}**")
            for n in notes:
                rown = st.columns([6, 1], vertical_alignment="center")
                with rown[0]:
                    st.write(n.text)
                with rown[1]:
                    if st.button("Delete", key=f"aa_note_del_{k}_{n.note_id}"):
                        run.aa_annotations[k] = [x for x in run.aa_annotations[k] if x.note_id != n.note_id]
                        if not run.aa_annotations[k]:
                            run.aa_annotations.pop(k, None)
                        run_log(run, "aa_note_deleted", {"aa": k, "note_id": n.note_id})
                        st.rerun()
    else:
        st.caption("No AA notes yet.")


# ---- Plot helpers (1/2) ----
def _add_iqr_band_and_median(
    fig: go.Figure,
    *,
    median: list[float | None],
    p25: list[float | None],
    p75: list[float | None],
    median_name: str,
    row: int | None = None,
    col: int | None = None,
) -> None:
    _add_trace(
        fig,
        go.Scatter(
            x=x,
            y=p75,
            mode="lines",
            name="P75",
            showlegend=False,
            hovertemplate="position=%{x}<br>P75=%{y:.6f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
    _add_trace(
        fig,
        go.Scatter(
            x=x,
            y=p25,
            mode="lines",
            name="IQR (P25–P75)",
            fill="tonexty",
            hovertemplate="position=%{x}<br>P25=%{y:.6f}<extra></extra>",
        ),
        row=row,
        col=col,
    )
    _add_trace(
        fig,
        go.Scatter(
            x=x,
            y=median,
            mode="lines",
            name=median_name,
            hovertemplate="position=%{x}<br>median=%{y:.6f}<extra></extra>",
        ),
        row=row,
        col=col,
    )


def _build_delta_figure(
    *,
    title: str,
    info_md: str,
    pairwise: dict[str, list[float | None]],
    delta_median: list[float | None],
    delta_p25: list[float | None],
    delta_p75: list[float | None],
    y_label: str,
    pair_prefix: str,
    show_regional_track: bool,
) -> go.Figure:
    _plot_header(title, info_md, show_titles=show_plot_titles, show_infos=show_plot_infos)

    if show_regional_track:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.25, 0.75],
            vertical_spacing=0.02,
        )
        _apply_regional_track(fig, assigned=assigned_regions, lane_count=lane_count, row=1, col=1)

        target_row, target_col = 2, 1
    else:
        fig = go.Figure()
        target_row, target_col = None, None

    # Pairwise traces
    if show_pairwise:
        for key, ys in pairwise.items():
            _add_trace(
                fig,
                go.Scatter(
                    x=x,
                    y=ys,
                    mode="lines",
                    name=f"{pair_prefix} {_pair_label(key)}",
                    hovertemplate=(
                        "position=%{x}<br>"
                        "|Δ|=%{y:.6f}<br>"
                        f"pair={_pair_label(key)}"
                        "<extra></extra>"
                    ),
                ),
                row=target_row,
                col=target_col,
            )

    # Summary
    if show_summary:
        _add_iqr_band_and_median(
            fig,
            median=delta_median,
            p25=delta_p25,
            p75=delta_p75,
            median_name=f"Median({pair_prefix})",
            row=target_row,
            col=target_col,
        )

    # Region hover carrier (ensures region block appears in unified hover)
    _add_trace(
        fig,
        go.Scatter(
            x=x,
            y=[0.0] * len(x),
            mode="markers",
            marker=dict(opacity=0.0, size=8),
            showlegend=False,
            customdata=region_hover_only,
            hovertemplate="%{customdata}<extra></extra>",
        ),
        row=target_row,
        col=target_col,
    )

    # Axes/layout
    if show_regional_track:
        fig.update_yaxes(range=[0, 1], fixedrange=True, title_text=y_label, row=2, col=1)
        fig.update_xaxes(fixedrange=False, title_text="Position", row=2, col=1)
    else:
        fig.update_layout(xaxis_title="Position", yaxis_title=y_label)
        fig.update_yaxes(range=[0, 1], fixedrange=True)
        fig.update_xaxes(fixedrange=False)

    fig.update_layout(
        hovermode="x unified",
        hoverlabel=dict(namelength=-1),
        uirevision=st.session_state["viz_uirevision"],
        showlegend=True,
    )
    apply_top_legend(fig)
    return fig


# ---- Plot 1 ----
fig_hp = _build_delta_figure(
    title=f"Pairwise Absolute Hydropathy Differences ({p.hp_scale_id})",
    info_md=(
        "- For each alignment column: pairwise absolute differences **|ΔHP|** between all sequence pairs.  \n"
        "- Summary: **Median(|ΔHP|)** with **IQR band (P25–P75)** across all pairs.  \n"
        "- **Gaps are treated as value 0** for HP."
    ),
    pairwise=p.hp_pairwise_delta,
    delta_median=p.hp_delta_median,
    delta_p25=p.hp_delta_p25,
    delta_p75=p.hp_delta_p75,
    y_label="|ΔHP| (pairwise, normalized)",
    pair_prefix="|ΔHP|",
    show_regional_track=show_reg_plot1,
)
st.plotly_chart(fig_hp, width="stretch")

# ---- Plot 2 ----
fig_pr = _build_delta_figure(
    title=f"Pairwise Absolute Polar Requirement Differences ({p.pr_scale_id})",
    info_md=(
        "- For each alignment column: pairwise absolute differences **|ΔPR|** between all sequence pairs.  \n"
        "- Summary: **Median(|ΔPR|)** with **IQR band (P25–P75)** across all pairs.  \n"
        "- **Gaps are treated as value 0** for PR."
    ),
    pairwise=p.pr_pairwise_delta,
    delta_median=p.pr_delta_median,
    delta_p25=p.pr_delta_p25,
    delta_p75=p.pr_delta_p75,
    y_label="|ΔPR| (pairwise, normalized)",
    pair_prefix="|ΔPR|",
    show_regional_track=show_reg_plot2,
)
st.plotly_chart(fig_pr, width="stretch")

# ---- Plot 3 (composition + regional track) ----
_plot_header(
    "Amino Acid Frequencies per Alignment Position",
    (
        "- Bottom track: stacked fractions of **amino acids + gaps** per alignment position.  \n"
        "- Top track: **regional annotations** (intervals) placed into lanes to avoid overlap.  \n"
        "- Hover includes **Amino acid note** and **Regional annotation** sections."
    ),
    show_titles=show_plot_titles,
    show_infos=show_plot_infos,
)

comp = p.composition_fraction

aa_gap_alphabet = [sym for sym, ys in comp.items() if any(v > 0.0 for v in ys)]
aa_gap_alphabet = sorted([sym for sym in aa_gap_alphabet if sym != "-"])
if "-" in comp and any(v > 0.0 for v in comp["-"]):
    aa_gap_alphabet.append("-")

AA_COLOR = {
    "A": "#1f77b4",
    "C": "#ff7f0e",
    "D": "#2ca02c",
    "E": "#d62728",
    "F": "#9467bd",
    "G": "#8c564b",
    "H": "#e377c2",
    "I": "#7f7f7f",
    "K": "#bcbd22",
    "L": "#17becf",
    "M": "#aec7e8",
    "N": "#ffbb78",
    "P": "#98df8a",
    "Q": "#ff9896",
    "R": "#c5b0d5",
    "S": "#c49c94",
    "T": "#f7b6d2",
    "V": "#c7c7c7",
    "W": "#dbdb8d",
    "Y": "#9edae5",
}
DEFAULT_AA_COLOR = "#999999"
GAP_COLOR = "rgba(128,128,128,0.3)"

aligned = run.alignment_result
seq_names = [s.name for s in aligned.sequences]
seq_strings = [s.aligned_sequence for s in aligned.sequences]
L = aligned.alignment_length

column_symbol_to_names: list[dict[str, list[str]]] = []
for col in range(L):
    m: dict[str, list[str]] = {}
    for nm, s in zip(seq_names, seq_strings):
        sym = s[col].upper()
        if sym in {".", "-"}:
            sym = "-"
        m.setdefault(sym, []).append(nm)
    column_symbol_to_names.append(m)

if show_reg_plot3:
    fig_c = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.25, 0.75],
        vertical_spacing=0.02,
    )
    _apply_regional_track(fig_c, assigned=assigned_regions, lane_count=lane_count, row=1, col=1)
    comp_row, comp_col = 2, 1
else:
    fig_c = go.Figure()
    comp_row, comp_col = None, None

for sym in aa_gap_alphabet:
    yvals = comp[sym]
    if sym == "-":
        _add_trace(
            fig_c,
            go.Bar(
                x=x,
                y=yvals,
                name="gap",
                marker=dict(color=GAP_COLOR),
                hoverinfo="skip",
            ),
            row=comp_row,
            col=comp_col,
        )
    else:
        _add_trace(
            fig_c,
            go.Bar(
                x=x,
                y=yvals,
                name=sym,
                marker=dict(color=AA_COLOR.get(sym, DEFAULT_AA_COLOR)),
                hoverinfo="skip",
            ),
            row=comp_row,
            col=comp_col,
        )

hover_per_col: list[str] = []
for i, pos in enumerate(x):
    lines = [f"<b>Position {pos}</b>"]

    present: list[tuple[str, float, list[str]]] = []
    occurring_symbols: list[str] = []

    for sym in aa_gap_alphabet:
        names_here = column_symbol_to_names[i].get(sym, [])
        if not names_here:
            continue
        frac = comp[sym][i]
        label = "gap" if sym == "-" else sym
        present.append((label, frac, names_here))
        occurring_symbols.append(sym)

    present.sort(key=lambda t: t[1], reverse=True)
    for label, frac, names_here in present:
        lines.append(f"{label}: {frac:.3f} — {_cap_list(names_here)}")

    aa_block = build_aa_note_block(occurring_symbols=occurring_symbols, aa_annotations=run.aa_annotations)
    lines.append(aa_block)

    regs_here = _regions_covering_position(run.regional_annotations, int(pos))
    lines.append(_format_region_hover_block(regs_here))

    hover_per_col.append("<br>".join(lines))

_add_trace(
    fig_c,
    go.Scatter(
        x=x,
        y=[1.0] * len(x),
        mode="markers",
        marker=dict(opacity=0.0, size=8),
        showlegend=False,
        customdata=hover_per_col,
        hovertemplate="%{customdata}<extra></extra>",
    ),
    row=comp_row,
    col=comp_col,
)

if show_reg_plot3:
    fig_c.update_yaxes(range=[0, 1], fixedrange=True, title_text="AA Frequencies", row=2, col=1)
    fig_c.update_xaxes(fixedrange=False, title_text="Position", row=2, col=1)
else:
    fig_c.update_layout(xaxis_title="Position", yaxis_title="AA Frequencies")
    fig_c.update_yaxes(range=[0, 1], fixedrange=True)
    fig_c.update_xaxes(fixedrange=False)

fig_c.update_layout(
    barmode="stack",
    hovermode="x unified",
    hoverlabel=dict(namelength=-1),
    uirevision=st.session_state["viz_uirevision"],
    showlegend=True,
)
apply_top_legend(fig_c)
st.plotly_chart(fig_c, width="stretch")
