# app.py
"""
Streamlit entry point.

Responsibilities:
- Initialize exactly one RunState in st.session_state["run"].
- Render the shared sidebar on this page as well.
- Provide a minimal "app" home view showing run summary + full event table.

Notes:
- All sidebar UI is centralized in pages/sidebar.py.
- Run creation + mandatory session_start logging is centralized in core/run_factory.py.
"""

from __future__ import annotations

import streamlit as st

from core.run_factory import create_new_run
from core.state import RunState
from ui.sidebar import render_sidebar


def _get_run() -> RunState:
    run = st.session_state.get("run")
    if run is None:
        run = create_new_run()
        st.session_state["run"] = run
    return run


def main() -> None:
    st.set_page_config(page_title="roiviz", layout="wide")

    run = _get_run()

    # Shared sidebar (available on all pages)
    render_sidebar(create_new_run)

    st.title("roiviz")
    st.info("Foundation: RunState + in-memory reproducibility log. No MAFFT/profiles/export yet (except log download).")

    st.subheader("Current run summary")
    st.json(
        {
            "run_id": run.run_id,
            "phase": run.phase.value,
            "created_at_utc": run.created_at_utc.isoformat(timespec="seconds"),
            "event_count": len(run.events),
            "inputs_committed": run.input_set is not None,
        }
    )

    st.subheader("All events")
    st.dataframe([e.to_dict() for e in run.events], width="stretch")


if __name__ == "__main__":
    main()
