"""
Input page (UI-only skeleton).

Rules:
- UI-only: widgets, navigation, rendering.
- No side effects: no subprocess, no HTTP, no filesystem writes.
- No heavy computation.
- Read-only access to st.session_state["run"].

Step 2 intent:
- Show the current run status and placeholders for input drafting.
- Do NOT commit inputs yet (pipeline not implemented).
"""

from __future__ import annotations

import streamlit as st


def _get_run():
    return st.session_state.get("run")


st.title("Step 1 — Input")

run = _get_run()
if run is None:
    st.error("RunState is missing. Please go to the main page (app.py) to initialize a run.")
    st.stop()

st.caption("UI-only skeleton. No validation, no commit, no GenBank/FASTA parsing yet.")

st.subheader("Run status")
st.json(
    {
        "run_id": run.run_id,
        "phase": run.phase.value,
        "event_count": len(run.events),
    }
)

st.divider()
st.subheader("Draft inputs (placeholder)")

st.info(
    "Planned: Add 2–10 AA sequences (manual / FASTA). "
    "Each entry will show status (invalid/valid) and metadata (length, name)."
)

with st.expander("What will exist here (planned)"):
    st.markdown(
        """
- Multi-entry input component (add/remove entries)
- For each entry:
  - name
  - AA sequence (validated/normalized)
  - status indicator
- Optional later:
  - GenBank fetch/upload + mat_peptide selection
"""
    )

st.divider()
st.subheader("Actions (disabled in Step 2)")

st.button(
    "Commit inputs (Next)",
    disabled=True,
    help="Disabled: pipeline.commit_inputs() not implemented yet (Step 3).",
)

st.caption("Next step: implement validation + commit_inputs action in core/pipeline.py.")
