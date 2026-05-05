from __future__ import annotations

import streamlit as st

from components import render_pipeline_navigator, render_processing_history_expander
from core.analysis.export import build_provenance_log_json, build_sequences_and_alignment_fasta
from core.analysis_session_io import import_session_from_json
from core.state import (
    clear_feedback,
    create_new_session,
    get_feedback,
    has_computed_profiles,
    has_valid_alignment,
    has_valid_input,
)


def _route_after_import(session: object) -> None:
    if has_computed_profiles(session) or has_valid_alignment(session):
        st.switch_page("pages/3_Analysis.py")
    elif has_valid_input(session):
        st.switch_page("pages/2_Alignment.py")
    else:
        st.switch_page("pages/1_Input.py")


@st.dialog("Start new session?", dismissible=False, icon=":material/warning:")
def _dialog_start_new() -> None:
    msg = (
        "Starting a new session will replace the current session. "
        "Unsaved work will be lost unless exported. "
        "This cannot be undone inside the app."
    )
    if st.session_state.get("ui_session_changed"):
        msg += " You have unexported changes."
    st.warning(msg)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel"):
            st.session_state["ui_home_show_new_confirm"] = False
            st.rerun()
    with c2:
        if st.button("Start new session", type="primary"):
            st.session_state["session"] = create_new_session()
            st.session_state["ui_session_changed"] = False
            st.session_state.pop("ui_sidebar_export_json", None)
            st.session_state["ui_home_show_new_confirm"] = False
            st.switch_page("pages/1_Input.py")


@st.dialog("Import session?", dismissible=False, icon=":material/warning:")
def _dialog_overwrite_import() -> None:
    msg = (
        "Importing will overwrite your current analysis session. "
        "All current work will be lost."
    )
    if st.session_state.get("ui_session_changed"):
        msg += " You have unexported changes."
    st.warning(msg)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel"):
            st.session_state["ui_import_show_confirm"] = False
            st.rerun()
    with c2:
        if st.button("Overwrite and import", type="primary"):
            pending_json = st.session_state.get("ui_import_pending_json", "")
            session = import_session_from_json(pending_json)
            if session is not None:
                st.session_state["session"] = session
                for k in list(st.session_state.keys()):
                    if k.startswith("ui_"):
                        del st.session_state[k]
                st.session_state["session"] = session
                _route_after_import(session)
            else:
                st.session_state["ui_import_show_confirm"] = False
                st.session_state["ui_import_error"] = (
                    "Import failed: file is not a valid session export. "
                    "Current session unchanged."
                )
                st.rerun()


session = st.session_state.get("session")

if session is not None:
    render_pipeline_navigator(session)

# Runtime feedback block
feedback = get_feedback()
if feedback:
    _dispatch = {"success": st.success, "error": st.error, "warning": st.warning}
    _dispatch.get(feedback["type"], st.info)(feedback["message"])
    clear_feedback()

st.title("Protein Sequence Analysis")

if session is not None:
    st.info(f"Active analysis session: {session.id}")

col1, col2 = st.columns(2)

with col1:
    if st.button("Start new analysis session", width="stretch"):
        if session is not None:
            st.session_state["ui_home_show_new_confirm"] = True
        else:
            st.session_state["session"] = create_new_session()
            st.session_state.pop("ui_sidebar_export_json", None)
            st.switch_page("pages/1_Input.py")
    if st.session_state.get("ui_home_show_new_confirm"):
        _dialog_start_new()

with col2:
    st.write("**Import existing session**")
    if err := st.session_state.pop("ui_import_error", None):
        st.error(err)

    uploaded_file = st.file_uploader("Select session JSON file", type=["json"], label_visibility="collapsed")

    if uploaded_file is None:
        st.session_state.pop("ui_import_pending_json", None)
        st.session_state.pop("ui_import_last_filename", None)
        st.session_state.pop("ui_import_show_confirm", None)
    else:
        filename = uploaded_file.name
        if st.session_state.get("ui_import_last_filename") != filename:
            try:
                raw = uploaded_file.read().decode("utf-8")
                st.session_state["ui_import_pending_json"] = raw
                st.session_state["ui_import_last_filename"] = filename
                if st.session_state.get("session") is not None:
                    st.session_state["ui_import_show_confirm"] = True
                else:
                    # No active session — import directly without confirmation.
                    loaded = import_session_from_json(raw)
                    if loaded is not None:
                        st.session_state["session"] = loaded
                        for k in list(st.session_state.keys()):
                            if k.startswith("ui_"):
                                del st.session_state[k]
                        st.session_state["session"] = loaded
                        _route_after_import(loaded)
                    else:
                        st.session_state["ui_import_error"] = (
                            "Import failed: file is not a valid session export."
                        )
                        st.rerun()
            except Exception:
                st.error("Import failed: file could not be read. Current session unchanged.")

    if st.session_state.get("ui_import_show_confirm"):
        _dialog_overwrite_import()

if session is not None:
    st.divider()

    # ── derived exports ───────────────────────────────────────────────────────

    with st.expander("Derived Exports"):
        st.write("**Provenance log**")
        if st.button("Generate provenance_log.json", key="home_gen_provenance"):
            st.session_state["ui_export_provenance"] = build_provenance_log_json(session)
            st.rerun()
        if prov_data := st.session_state.get("ui_export_provenance"):
            st.download_button(
                "Download provenance_log.json",
                data=prov_data,
                file_name="provenance_log.json",
                mime="application/json",
                key="home_dl_provenance",
            )

        st.divider()
        st.write("**Sequences and alignment FASTA**")
        if has_valid_alignment(session):
            if st.button("Generate sequences_and_alignment.fasta", key="home_gen_fasta"):
                st.session_state["ui_export_fasta"] = build_sequences_and_alignment_fasta(session)
                st.rerun()
            if fasta_data := st.session_state.get("ui_export_fasta"):
                st.download_button(
                    "Download sequences_and_alignment.fasta",
                    data=fasta_data,
                    file_name="sequences_and_alignment.fasta",
                    mime="text/plain",
                    key="home_dl_fasta",
                )
        else:
            st.caption("Not available: complete alignment first.")

    render_processing_history_expander(session)
