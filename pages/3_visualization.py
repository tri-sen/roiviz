# pages/3_visualization.py
from __future__ import annotations

import uuid

import plotly.graph_objects as go
import streamlit as st

from core.export_bundle import build_export_zip_bytes
from core.pipeline import PipelineError, compute_profiles
from core.run_factory import create_new_run
from core.run_log import run_log
from ui.sidebar import render_sidebar


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


def _plot_header_with_info(title: str, info_md: str) -> None:
    st.markdown(f"##### {title}")
    with st.expander("ℹ️ What this shows", expanded=False):
        st.markdown(info_md)


def apply_top_legend(fig: go.Figure) -> None:
    """
    Put legend above the plot area (outside the plotting region).
    """
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
x = p.aa_position

if "viz_uirevision" not in st.session_state:
    st.session_state["viz_uirevision"] = "keep"

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
            # Log BEFORE build so provenance includes the export action
            run_log(
                run,
                "export_requested",
                {"page": "visualization", "kind": "zip_bundle"},
            )

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
                run_log(
                    run,
                    "export_failed",
                    {"error": str(e)},
                    level="ERROR",
                )
                st.error(f"Export failed: {e}")

st.caption(
    "Plot 1/2: pairwise |Δ| + median(|Δ|) with IQR band (P25–P75), y fixed [0,1]. "
    "Plot 3: stacked AA/gap fractions, y fixed [0,1]."
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


def _add_iqr_band_and_median(
    fig: go.Figure,
    *,
    median: list[float | None],
    p25: list[float | None],
    p75: list[float | None],
    median_name: str,
) -> None:
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
    pairwise: dict[str, list[float | None]],
    delta_median: list[float | None],
    delta_p25: list[float | None],
    delta_p75: list[float | None],
    y_label: str,
    pair_prefix: str,
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
        xaxis_title="Position",
        yaxis_title=y_label,
        hovermode="x unified",
        hoverlabel=dict(namelength=-1),
        yaxis=dict(range=[0, 1], fixedrange=True),
        xaxis=dict(fixedrange=False),
        uirevision=st.session_state["viz_uirevision"],
        showlegend=True,
    )
    apply_top_legend(fig)
    return fig


# ---- Plot 1 ----
_plot_header_with_info(
    f"Pairwise Absolute Hydropathy Differences ({p.hp_scale_id})",
    (
        "**What this shows**  \n"
        "- For each alignment column: pairwise absolute differences **|ΔHP|** between all sequence pairs.  \n"
        "- Summary: **Median(|ΔHP|)** with **IQR band (P25–P75)** across all pairs.  \n"
        "- **Gaps are treated as value 0** for HP."
    ),
)
fig_hp = _plot_delta(
    pairwise=p.hp_pairwise_delta,
    delta_median=p.hp_delta_median,
    delta_p25=p.hp_delta_p25,
    delta_p75=p.hp_delta_p75,
    y_label="|ΔHP| (pairwise, normalized)",
    pair_prefix="|ΔHP|",
)
st.plotly_chart(fig_hp, width="stretch")

# ---- Plot 2 ----
_plot_header_with_info(
    f"Pairwise Absolute Polar Requirement Differences ({p.pr_scale_id})",
    (
        "**What this shows**  \n"
        "- For each alignment column: pairwise absolute differences **|ΔPR|** between all sequence pairs.  \n"
        "- Summary: **Median(|ΔPR|)** with **IQR band (P25–P75)** across all pairs.  \n"
        "- **Gaps are treated as value 0** for PR."
    ),
)
fig_pr = _plot_delta(
    pairwise=p.pr_pairwise_delta,
    delta_median=p.pr_delta_median,
    delta_p25=p.pr_delta_p25,
    delta_p75=p.pr_delta_p75,
    y_label="|ΔPR| (pairwise, normalized)",
    pair_prefix="|ΔPR|",
)
st.plotly_chart(fig_pr, width="stretch")

# ---- Plot 3 ----
_plot_header_with_info(
    "Amino Acid Frequencies per Alignment Position",
    (
        "**What this shows**  \n"
        "- For each alignment position, the stacked bar shows the relative frequencies of amino acids (and gaps) observed at that position.  \n"
        "- Hover lists only show amino acids actually present at that position and which sequences contribute them.  \n"
        "- Gap bars are **grey with 30% opacity**."
    ),
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

fig_c = go.Figure()

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

hover_per_col: list[str] = []
for i, pos in enumerate(x):
    lines = [f"<b>Position {pos}</b>"]

    present: list[tuple[str, float, list[str]]] = []
    for sym in aa_gap_alphabet:
        names_here = column_symbol_to_names[i].get(sym, [])
        if not names_here:
            continue
        frac = comp[sym][i]
        label = "gap" if sym == "-" else sym
        present.append((label, frac, names_here))

    present.sort(key=lambda t: t[1], reverse=True)

    for label, frac, names_here in present:
        lines.append(f"{label}: {frac:.3f} — {_cap_list(names_here)}")

    hover_per_col.append("<br>".join(lines))

fig_c.add_trace(
    go.Scatter(
        x=x,
        y=[1.0] * len(x),
        mode="markers",
        marker=dict(opacity=0.0, size=8),
        showlegend=False,
        customdata=hover_per_col,
        hovertemplate="%{customdata}<extra></extra>",
    )
)

fig_c.update_layout(
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
apply_top_legend(fig_c)
st.plotly_chart(fig_c, width="stretch")
