# pages/3_visualization.py
from __future__ import annotations

import uuid

import plotly.graph_objects as go
import streamlit as st

from core.pipeline import PipelineError, compute_profiles
from core.run_factory import create_new_run
from ui.sidebar import render_sidebar


def _tooltip_h3(text: str, tooltip: str) -> None:
    # Streamlit has no native "tooltip on header", so use HTML title.
    st.markdown(f'<h3 title="{tooltip}">{text}</h3>', unsafe_allow_html=True)


def _pair_label(pair_key: str) -> str:
    # pair_key format: "seqA__vs__seqB"
    a, b = pair_key.split("__vs__", 1)
    return f"{a}–{b}"


def _cap_list(items: list[str], limit: int = 12) -> str:
    if not items:
        return "-"
    if len(items) <= limit:
        return ", ".join(items)
    head = ", ".join(items[:limit])
    return f"{head}, … (+{len(items) - limit})"


# ---- Layout helpers: keep visual plot widths aligned across Plot 1/2/3 ----
LEGEND_SLOT_R = 340  # fixed right space (px-ish) reserved for legend on ALL plots


def apply_right_legend_slot(fig: go.Figure) -> None:
    """
    Reserve a fixed right margin so the plot area (x-axis visual width)
    remains equal across figures, even if legends differ in content.
    """
    fig.update_layout(
        legend=dict(
            x=1.02,
            xanchor="left",
            y=1.0,
            yanchor="top",
            itemsizing="constant",
            traceorder="normal",
        ),
        margin=dict(l=60, r=LEGEND_SLOT_R, t=60, b=60),
    )


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
    if st.button("Compute profiles", type="primary"):
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
x = p.positions_1based  # 1-based alignment columns

if "viz_uirevision" not in st.session_state:
    st.session_state["viz_uirevision"] = "keep"

top_cols = st.columns([1, 2])
with top_cols[0]:
    if st.button("Reset X-Axis zoom (on all plots)"):
        st.session_state["viz_uirevision"] = str(uuid.uuid4())
        st.rerun()

show_pairwise = st.checkbox("Show pairwise |Δ| lines (can be noisy)", value=True)
show_summary = st.checkbox("Show median + IQR band (P25–P75)", value=True)


def _add_iqr_band_and_median(
    fig: go.Figure,
    *,
    median: list[float | None],
    p25: list[float | None],
    p75: list[float | None],
    median_name: str,
) -> None:
    # Upper bound (hidden in legend) -> then lower bound filled to it -> IQR band
    fig.add_trace(
        go.Scatter(
            x=x,
            y=p75,
            mode="lines",
            name="P75",
            showlegend=False,
            hovertemplate="col=%{x}<br>P75=%{y:.6f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=p25,
            mode="lines",
            name="IQR (P25–P75)",
            fill="tonexty",
            hovertemplate="col=%{x}<br>P25=%{y:.6f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=median,
            mode="lines",
            name=median_name,
            hovertemplate="col=%{x}<br>median=%{y:.6f}<extra></extra>",
        )
    )


def _plot_delta(
    *,
    title: str,
    pairwise: dict[str, list[float | None]],
    delta_median: list[float | None],
    delta_p25: list[float | None],
    delta_p75: list[float | None],
    y_label: str,
    pair_prefix: str,  # "|ΔHP|" or "|ΔPR|"
) -> go.Figure:
    fig = go.Figure()

    if show_pairwise:
        for key, ys in pairwise.items():
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=ys,
                    mode="lines",
                    name=f"{pair_prefix} {_pair_label(key)}",
                    hovertemplate=(
                        "col=%{x}<br>"
                        "|Δ|=%{y:.6f}<br>"
                        f"pair={_pair_label(key)}"
                        "<extra></extra>"
                    ),
                )
            )

    if show_summary:
        _add_iqr_band_and_median(
            fig,
            median=delta_median,
            p25=delta_p25,
            p75=delta_p75,
            median_name=f"Median({pair_prefix})",
        )

    fig.update_layout(
        title=title,
        xaxis_title="Position",
        yaxis_title=y_label,
        hovermode="x unified",
        hoverlabel=dict(namelength=-1),
        yaxis=dict(range=[0, 1], fixedrange=True),
        xaxis=dict(fixedrange=False),
        uirevision=st.session_state["viz_uirevision"],
        showlegend=True,
    )
    apply_right_legend_slot(fig)
    return fig


# ---- Plot 1: |ΔHP|
fig_hp = _plot_delta(
    title=f"Pairwise Absolute Hydropathy Differences ({p.hp_scale_id})",
    pairwise=p.hp_pairwise_delta,
    delta_median=p.hp_delta_median,
    delta_p25=p.hp_delta_p25,
    delta_p75=p.hp_delta_p75,
    y_label="|ΔH| (pairwise, normalized)",
    pair_prefix="|ΔHP|",
)
st.plotly_chart(fig_hp, width="stretch")


# ---- Plot 2: |ΔPR|
fig_pr = _plot_delta(
    title=f"Pairwise Absolute Polar Requirement Differences ({p.pr_scale_id})",
    pairwise=p.pr_pairwise_delta,
    delta_median=p.pr_delta_median,
    delta_p25=p.pr_delta_p25,
    delta_p75=p.pr_delta_p75,
    y_label="|ΔPR| (pairwise, normalized)",
    pair_prefix="|ΔPR|",
)
st.plotly_chart(fig_pr, width="stretch")


# ---- Plot 3: composition (stacked) with a single hover carrier (no "null" spam)

comp = p.composition_fraction

# Stable alphabet = observed AAs sorted + gap at end if present
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

# column_symbol_to_names[i][sym] -> list of sequence names
column_symbol_to_names: list[dict[str, list[str]]] = []
for col in range(L):
    m: dict[str, list[str]] = {}
    for nm, s in zip(seq_names, seq_strings):
        sym = s[col].upper()
        if sym in {".", "-"}:
            sym = "-"
        m.setdefault(sym, []).append(nm)
    column_symbol_to_names.append(m)

fig_c = go.Figure()

# Bars: no hover (prevents unified-hover "null" spam)
for sym in aa_gap_alphabet:
    yvals = comp[sym]
    if sym == "-":
        fig_c.add_trace(
            go.Bar(
                x=x,
                y=yvals,
                name="gap",
                marker=dict(color=GAP_COLOR),
                hoverinfo="skip",
            )
        )
    else:
        fig_c.add_trace(
            go.Bar(
                x=x,
                y=yvals,
                name=sym,
                marker=dict(color=AA_COLOR.get(sym, DEFAULT_AA_COLOR)),
                hoverinfo="skip",
            )
        )

# Hover carrier: one hover box per column listing ONLY present symbols
hover_per_col: list[str] = []
for i, pos in enumerate(x):
    lines = [f"<b>Position {pos}</b>"]

    present: list[tuple[str, float, list[str]]] = []
    for sym in aa_gap_alphabet:
        names_here = column_symbol_to_names[i].get(sym, [])
        if not names_here:
            continue
        frac = comp[sym][i]  # display only
        label = "gap" if sym == "-" else sym
        present.append((label, frac, names_here))

    present.sort(key=lambda t: t[1], reverse=True)

    for label, frac, names_here in present:
        lines.append(f"{label}: {frac:.3f} — {_cap_list(names_here)}")

    hover_per_col.append("<br>".join(lines))

fig_c.add_trace(
    go.Scatter(
        x=x,
        y=[1.0] * len(x),  # arbitrary; invisible anyway
        mode="markers",
        marker=dict(opacity=0.0, size=8),
        showlegend=False,
        customdata=hover_per_col,
        hovertemplate="%{customdata}<extra></extra>",
    )
)

fig_c.update_layout(
    title="Position-Specific Amino Acid Frequencies",
    xaxis_title="Position",
    yaxis_title="AA Frequencies",
    barmode="stack",
    hovermode="x unified",
    hoverlabel=dict(namelength=-1),
    yaxis=dict(range=[0, 1], fixedrange=True),
    xaxis=dict(fixedrange=False),
    uirevision=st.session_state["viz_uirevision"],
    showlegend=True,
)
apply_right_legend_slot(fig_c)

st.plotly_chart(fig_c, width="stretch")
