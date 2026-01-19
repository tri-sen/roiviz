from __future__ import annotations

import streamlit as st

from core.run_factory import create_new_run
from ui.sidebar import render_sidebar


def _get_run():
    return st.session_state.get("run")


st.title("Step 3 — Visualization (placeholder)")

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

if run.alignment_result is None:
    st.warning("No alignment yet. Go to Step 2 and run MAFFT.")
    st.stop()

ar = run.alignment_result
st.success("Alignment is available. Next step is profile computation (not implemented yet).")

st.write("Alignment summary")
st.json(
    {
        "alignment_length": ar.alignment_length,
        "sequence_count": len(ar.sequences),
        "tool_version": ar.execution.tool_version,
        "duration_seconds": ar.execution.duration_seconds,
    }
)

with st.expander("Aligned sequences (FASTA)", expanded=False):
    for s in ar.sequences:
        st.markdown(f"**{s.name}**")
        st.code(s.aligned_sequence)

st.info("Next: implement ComputedProfiles + plots + export on this page.")
