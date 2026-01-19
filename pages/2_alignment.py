from __future__ import annotations

import streamlit as st

from core.models import AlignmentParams
from core.pipeline import PipelineError, run_alignment
from core.run_factory import create_new_run
from ui.sidebar import render_sidebar  # falls du es so benannt hast


def _get_run():
    return st.session_state.get("run")


st.title("Step 2 — Alignment (MAFFT)")

run = _get_run()
if run is None:
    st.error("RunState is missing. Go to the main page (app.py) to initialize a run.")
    st.stop()

render_sidebar(create_new_run)

st.subheader("Run status")
st.json(
    {
        "run_id": run.run_id,
        "phase": run.phase.value,
        "event_count": len(run.events),
        "inputs_committed": run.input_set is not None,
        "alignment_done": run.alignment_result is not None,
    }
)

# Guard: inputs must be committed
if run.input_set is None:
    st.warning("No inputs committed yet. Go to Step 1 and commit inputs first.")
    st.stop()

# If alignment already exists: show it, disable rerun
if run.alignment_result is not None:
    ar = run.alignment_result
    st.success("Alignment already exists for this run (read-only). Start a New run to change it.")

    st.write("Alignment summary")
    st.json(
        {
            "alignment_length": ar.alignment_length,
            "sequence_count": len(ar.sequences),
            "return_code": ar.execution.return_code,
            "tool_version": ar.execution.tool_version,
            "duration_seconds": ar.execution.duration_seconds,
        }
    )

    if ar.execution.stderr_preview:
        st.text_area("MAFFT stderr (preview)", ar.execution.stderr_preview, height=180)

    with st.expander("Aligned sequences (FASTA)", expanded=False):
        for s in ar.sequences:
            st.markdown(f"**{s.name}**")
            st.code(s.aligned_sequence)

    st.stop()

# Guard: must be in ALIGNMENT phase
if run.phase.value != "alignment":
    st.warning(f"Phase is '{run.phase.value}'. Expected 'alignment'.")
    st.info("If you committed inputs, phase should already be ALIGNMENT. Otherwise start a New run.")
    st.stop()

st.divider()
st.subheader("Parameters (MVP)")

# MVP defaults: keep it simple
threads = st.number_input("Threads", min_value=1, max_value=8, value=1, step=1)
use_recommended = st.checkbox("Use recommended settings", value=True)

custom_args_text = st.text_input(
    "Custom MAFFT args (space-separated)",
    value="--auto" if use_recommended else "",
    help="Example: --auto  (Keep minimal for MVP.)",
)

args = [a for a in custom_args_text.strip().split() if a.strip()]
params = AlignmentParams(tool="mafft", threads=int(threads), args=args, label="recommended" if use_recommended else "custom")

st.divider()
st.subheader("Run")

can_run = True
disabled_reason = None

if run.alignment_locked:
    can_run = False
    disabled_reason = "Alignment is locked for this run."
if run.input_set is None or not run.inputs_locked:
    can_run = False
    disabled_reason = "Inputs are not committed."
if run.alignment_result is not None:
    can_run = False
    disabled_reason = "Alignment already exists."

if not can_run:
    st.warning(disabled_reason or "Cannot run alignment.")
    st.button("Run alignment", disabled=True)
else:
    if st.button("Run alignment", type="primary"):
        try:
            with st.spinner("Running MAFFT..."):
                run_alignment(run=run, params=params, timeout_seconds=120)
            st.success("Alignment completed. Phase advanced to VISUALIZATION.")
            st.rerun()
        except PipelineError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Unexpected error: {e}")
