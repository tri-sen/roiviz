"""
Visualization page (UI-only skeleton).

Rules:
- UI-only rendering.
- No heavy computation (profiles are computed in core/profiles via core/pipeline later).
- Export is an option here (not a separate page), but disabled for now.

Step 2 intent:
- Show placeholders for plots, annotations, and export.
"""

from __future__ import annotations

import streamlit as st


def _get_run():
    return st.session_state.get("run")


st.title("Step 3 — Visualization")

run = _get_run()
if run is None:
    st.error("RunState is missing. Please go to the main page (app.py) to initialize a run.")
    st.stop()

st.caption("UI-only skeleton. No profile computation, no plots yet.")

st.subheader("Run status")
st.json(
    {
        "run_id": run.run_id,
        "phase": run.phase.value,
        "event_count": len(run.events),
    }
)

st.divider()
st.subheader("Plots (placeholders)")

st.info(
    "Planned plots (shared x-axis = alignment columns, 1-based):\n"
    "- Hydropathy: median + IQR\n"
    "- Polar requirement: median + IQR\n"
    "- Composition: AA fractions + gap fraction"
)

with st.expander("Annotations (planned)"):
    st.markdown(
        """
- Region annotations in alignment-column coordinates (1-based, inclusive)
- Create/delete annotations
- Warning/label: annotations refer to alignment columns (including gaps)
"""
    )

st.divider()
st.subheader("Actions (disabled in Step 2)")

st.button(
    "Compute profiles",
    disabled=True,
    help="Disabled: core/profiles + pipeline.compute_profiles() not implemented yet (Step 5).",
)

with st.expander("Export (disabled placeholder)"):
    st.button(
        "Create export bundle",
        disabled=True,
        help="Disabled: export integration not implemented yet (Step 6).",
    )
    st.caption("Export will include inputs, alignment, computed profiles, annotations, and the reproducibility log.")

st.caption("Next: implement compute_profiles + plotting + export in later steps.")
