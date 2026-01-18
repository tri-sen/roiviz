"""
Alignment page (UI-only skeleton).

Rules:
- UI-only rendering.
- No subprocess calls (MAFFT must run in core/integrations via core/pipeline later).
- Read-only access to st.session_state["run"].

Step 2 intent:
- Show prerequisites and placeholders for MAFFT configuration + alignment preview.
"""

from __future__ import annotations

import streamlit as st


def _get_run():
    return st.session_state.get("run")


st.title("Step 2 — Alignment")

run = _get_run()
if run is None:
    st.error("RunState is missing. Please go to the main page (app.py) to initialize a run.")
    st.stop()

st.caption("UI-only skeleton. No MAFFT execution yet.")

st.subheader("Run status")
st.json(
    {
        "run_id": run.run_id,
        "phase": run.phase.value,
        "event_count": len(run.events),
    }
)

st.divider()
st.subheader("Prerequisites (planned)")
st.markdown(
    """
- Inputs must be committed (InputSet exists and is locked).
- Alignment runs once per run.
"""
)

st.divider()
st.subheader("MAFFT configuration (placeholder)")
st.info(
    "Planned: choose tool (MAFFT v7 only for MVP), show recommended params, "
    "optional custom params."
)

with st.expander("Alignment preview (planned)"):
    st.markdown(
        """
- After MAFFT finishes:
  - show aligned FASTA (expandable per sequence)
  - show alignment length
  - show execution summary (return code, stderr preview)
"""
    )

st.divider()
st.subheader("Actions (disabled in Step 2)")

st.button(
    "Run alignment",
    disabled=True,
    help="Disabled: MAFFT integration + pipeline.run_alignment() not implemented yet (Step 4).",
)

st.caption("Next: after Step 3 (commit inputs), implement MAFFT integration + alignment action.")
