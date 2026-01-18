"""
Streamlit entry point (Step 1).

Responsibilities:
- Initialize exactly one RunState in st.session_state["run"].
- Append exactly one 'session_start' event per new run_id (no rerun spam).
- Provide sidebar controls: show run_id/phase, "New run", log preview + JSONL download.

Non-negotiable:
- No business logic (no MAFFT, no profiles).
- Side effects must be explicit. Logging is in-memory only in Step 1.
"""

from __future__ import annotations

import streamlit as st

from core.provenance import append_event, export_events_jsonl, session_start_payload
from core.state import RunState


def _create_new_run() -> RunState:
    run = RunState.new()
    append_event(
        run=run,
        event="session_start",
        data=session_start_payload(),
        level="INFO",
    )
    return run


def _get_run() -> RunState:
    run = st.session_state.get("run")
    if run is None:
        run = _create_new_run()
        st.session_state["run"] = run
    return run


def main() -> None:
    st.set_page_config(page_title="roiviz", layout="wide")

    run = _get_run()

    with st.sidebar:
        st.header("Run")
        st.write(f"run_id: `{run.run_id}`")
        st.write(f"phase: `{run.phase.value}`")

        if st.button("New run", type="primary"):
            st.session_state["run"] = _create_new_run()
            st.rerun()

        st.divider()
        st.subheader("Reproducibility log")
        st.caption("In-memory log (append-only). Logged only on explicit actions.")

        # Show a small preview
        preview = [e.to_dict() for e in run.events[-10:]]
        st.json(preview)

        # Download full JSONL
        jsonl_text = export_events_jsonl(run.events)
        st.download_button(
            label="Download log (JSONL)",
            data=jsonl_text.encode("utf-8"),
            file_name=f"provenance_{run.run_id}.jsonl",
            mime="application/jsonl",
        )

    st.title("roiviz — Step 1")
    st.info("Foundation only: RunState + in-memory reproducibility log. No MAFFT/profiles yet.")

    st.write("Current run summary:")
    st.json(
        {
            "run_id": run.run_id,
            "phase": run.phase.value,
            "event_count": len(run.events),
        }
    )

    st.write("All events:")
    st.dataframe([e.to_dict() for e in run.events], use_container_width=True)


if __name__ == "__main__":
    main()
