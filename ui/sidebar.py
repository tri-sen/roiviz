"""
Shared UI components (pages/ only).

Rules:
- UI-only. May import streamlit.
- Must not perform heavy computation or side effects.
"""

from __future__ import annotations

import streamlit as st

from core.provenance import export_events_jsonl


def get_run():
    return st.session_state.get("run")


def render_sidebar(create_new_run_func) -> None:
    """
    Render a standard sidebar on every page.

    create_new_run_func: callable () -> RunState
    """
    run = get_run()

    with st.sidebar:
        st.header("Run")

        if run is None:
            st.warning("RunState missing. Open the main page to initialize a run.")
            return

        st.write(f"run_id: `{run.run_id}`")
        st.write(f"phase: `{run.phase.value}`")

        if st.button("New run", type="primary"):
            # Clear UI-owned draft state so it cannot bleed into the new run
            if "draft_inputs" in st.session_state:
                del st.session_state["draft_inputs"]

            st.session_state["run"] = create_new_run_func()
            st.rerun()

        st.divider()
        st.subheader("Reproducibility log")
        st.caption("In-memory log. Logged only on explicit actions.")

        st.json([e.to_dict() for e in run.events[-10:]])

        jsonl_text = export_events_jsonl(run.events)
        st.download_button(
            label="Download log (JSONL)",
            data=jsonl_text.encode("utf-8"),
            file_name=f"provenance_{run.run_id}.jsonl",
            mime="application/jsonl",
        )
