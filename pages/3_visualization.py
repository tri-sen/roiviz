from __future__ import annotations

import uuid

import streamlit as st
import plotly.graph_objects as go

from core.pipeline import PipelineError, compute_profiles
from core.run_factory import create_new_run
from ui.sidebar import render_sidebar


def _get_run():
    return st.session_state.get("run")


def _pair_label(pair_key: str) -> str:
    # pair_key: "seqA__vs__seqB" -> "seqA–seqB"
    a, b = pair_key.split("__vs__", 1)
    return f"{a}–{b}"


st.title("Step 3 — Visualization")

run = _get_run()
if run is None:
    st.error("RunState is missing. Go to the main page (app.py) to initialize a run.")
    st.stop()

render_sidebar(create_new_run)

if run.alignment_result is None:
    st.warning("No alignment yet. Go to Step 2 and run MAFFT.")
    st.stop()

if run.computed_profiles is None:
    if st.button("Compute profiles", type="primary"):
        try:
            with st.spinner("Computing profiles..."):
                compute_profiles(run)
            st.success("Profiles computed.")
            st.rerun()
        except PipelineError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Unexpected error: {e}")
    st.stop()

p = run.computed_profiles
x = p.positions_1based

# reset zoom for all plots via uirevision
if "viz_uirevision" not in st.session_state:
    st.session_state["viz_uirevision"] = "keep"

cols = st.columns([1, 2])
with cols[0]:
    if st.button("Reset X zoom (all plots)"):
        st.session_state["viz_uirevision"] = str(uuid.uuid4())
        st.rerun()
with cols[1]:
    st.caption("Plot 1/2: pairwise |Δ| + median(|Δ|) with IQR band (P25–P75). y fixed to [0,1].")

show_pairwise = st.checkbox("Show pairwise |Δ| lines (can be noisy)", value=True)
show_summary = st.checkbox("Show median + IQR band (P25–P75)", value=True)


def _add_iqr_band_and_median(fig: go.Figure, *, median, p25, p75, median_name: str) -> None:
    # Upper bound (no legend)
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
    # Lower bound filled to previous => band
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
    # Median line
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
    delta_median,
    delta_p25,
    delta_p75,
    y_label: str,
    pair_prefix: str,  # "|ΔH|" or "|ΔPR|"
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
                    hovertemplate="col=%{x}<br>|Δ|=%{y:.6f}<br>pair=" + _pair_label(key) + "<extra></extra>",
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
        xaxis_title="Alignment column (1-based)",
        yaxis_title=y_label,
        hovermode="x unified",
        hoverlabel=dict(namelength=-1),
        legend_title_text="",
        yaxis=dict(range=[0, 1], fixedrange=True),
        xaxis=dict(fixedrange=False),
        uirevision=st.session_state["viz_uirevision"],
    )
    return fig


fig_hp = _plot_delta(
    title=f"Pairwise Absolute Hydropathy Differences",
    pairwise=p.hp_pairwise_delta,
    delta_median=p.hp_delta_median,
    delta_p25=p.hp_delta_p25,
    delta_p75=p.hp_delta_p75,
    y_label="|ΔH| (pairwise, normalized)",
    pair_prefix="|ΔH|",
)
st.plotly_chart(fig_hp, width="stretch")

fig_pr = _plot_delta(
    title=f"Pairwise Absolute Polar Requirement Differences",
    pairwise=p.pr_pairwise_delta,
    delta_median=p.pr_delta_median,
    delta_p25=p.pr_delta_p25,
    delta_p75=p.pr_delta_p75,
    y_label="|ΔPR| (pairwise, normalized)",
    pair_prefix="|ΔPR|",
)
st.plotly_chart(fig_pr, width="stretch")

st.markdown("### Plot 3 — Composition (stacked fractions; gaps grey 30%)")
comp = p.composition_fraction
alignment_alphabet = [sym for sym, ys in comp.items() if any(v > 0.0 for v in ys)]
alignment_alphabet = sorted([sym for sym in alignment_alphabet if sym != "-"]) + (["-"] if "-" in alignment_alphabet else [])

fig_c = go.Figure()
for sym in alignment_alphabet:
    if sym == "-":
        fig_c.add_trace(
            go.Bar(
                x=x,
                y=comp[sym],
                name="gap",
                marker=dict(color="rgba(128,128,128,0.3)"),
                hovertemplate="col=%{x}<br>gap_fraction=%{y:.6f}<extra></extra>",
            )
        )
    else:
        fig_c.add_trace(
            go.Bar(
                x=x,
                y=comp[sym],
                name="aa",
                hovertemplate="col=%{x}<br>fraction=%{y:.6f}<br>aa=" + sym + "<extra></extra>",
            )
        )

fig_c.update_layout(
    title="AA / gap composition per alignment column",
    xaxis_title="Position",
    yaxis_title="Fraction (0..1)",
    barmode="stack",
    hovermode="x unified",
    hoverlabel=dict(namelength=-1),
    yaxis=dict(range=[0, 1], fixedrange=True),
    xaxis=dict(fixedrange=False),
    uirevision=st.session_state["viz_uirevision"],
)
st.plotly_chart(fig_c, width="stretch")
