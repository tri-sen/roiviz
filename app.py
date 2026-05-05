import streamlit as st

from core.analysis_session_io import export_session_to_json

st.set_page_config(page_title="Protein Sequence Analysis", layout="wide")

pg = st.navigation(
    [
        st.Page("home.py", title="Home", default=True),
        st.Page("pages/1_Input.py", title="Input"),
        st.Page("pages/2_Alignment.py", title="Alignment"),
        st.Page("pages/3_Analysis.py", title="Analysis"),
    ],
    position="hidden",
)

with st.sidebar:
    st.subheader("Session")
    _sidebar_session = st.session_state.get("session")
    if _sidebar_session is None:
        st.caption("No active session to export.")
    else:
        if st.button(
            "Export current session",
            key="ui_sidebar_export_btn",
            help=(
                "Export the canonical analysis_session.json file. "
                "This file can be imported later to reload the analysis session. "
                "Derived CSV, FASTA, and provenance exports are inspection/report files "
                "and are not reload formats."
            ),
        ):
            _json_str = export_session_to_json(_sidebar_session)
            if _json_str is not None:
                st.session_state["ui_sidebar_export_json"] = _json_str
                st.session_state["ui_session_changed"] = False
            else:
                st.session_state.pop("ui_sidebar_export_json", None)
                st.session_state["ui_sidebar_export_error"] = (
                    "Export failed: session is not in a valid state."
                )
            st.rerun()
        if _export_err := st.session_state.pop("ui_sidebar_export_error", None):
            st.error(_export_err)
        if _export_json := st.session_state.get("ui_sidebar_export_json"):
            st.download_button(
                label="Download analysis_session.json",
                data=_export_json,
                file_name=f"session_{_sidebar_session.id}.json",
                mime="application/json",
                key="ui_sidebar_export_dl",
            )

    st.subheader("Display")
    st.checkbox("Show processing history", value=False, key="show_processing_history")

pg.run()
