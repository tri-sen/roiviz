from __future__ import annotations

import streamlit as st

from core.alignment.service import reopen_alignment, run_alignment
from core.analysis.profiles import compute_profiles
from core.analysis_session_models import AlignmentStatus
from core.state import (
    clear_feedback,
    get_feedback,
    get_session,
    has_computed_profiles,
    has_valid_alignment,
    has_valid_input,
    mark_session_changed,
    set_feedback,
)
from components import (
    render_aligned_sequences_expander,
    render_pipeline_navigator,
    render_processing_history_expander,
    render_selected_sequences_expander,
    render_workflow_box,
)


@st.dialog("Reopen alignment stage?", dismissible=False, icon=":material/warning:")
def _dialog_reopen_alignment() -> None:
    st.warning(
        "Reopening alignment will delete the analysis results. "
        "This cannot be undone inside the app."
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel"):
            st.session_state["ui_alignment_show_reopen_confirm"] = False
            st.rerun()
    with c2:
        if st.button("Delete downstream data and reopen", type="primary"):
            from core.state import get_session as _get_session
            reopen_alignment(_get_session())
            mark_session_changed()
            st.session_state["ui_alignment_show_reopen_confirm"] = False
            st.session_state.pop("ui_alignment_analysis_error_msg", None)
            set_feedback("info", "Alignment cleared. Ready to align again.")
            st.rerun()


if "session" not in st.session_state:
    st.error("No active session. Go to the home page to start one.")
    st.stop()

session = get_session()
render_pipeline_navigator(session, "alignment")

st.title("Step 2: Alignment")

# Runtime feedback block
feedback = get_feedback()
if feedback:
    _dispatch = {"success": st.success, "error": st.error, "warning": st.warning}
    _dispatch.get(feedback["type"], st.info)(feedback["message"])
    clear_feedback()

render_workflow_box(session, "alignment")

# ── selected input sequences (always shown) ───────────────────────────────────

render_selected_sequences_expander(session)

if not has_valid_input(session):
    pass
else:
    stage = session.alignment_stage

    # ── success (read-only) view ──────────────────────────────────────────────

    if has_valid_alignment(session):
        st.success(
            f"Alignment complete: {len(stage.aligned_sequences)} sequences, "
            f"{stage.alignment_length} positions."
        )

        # Alignment summary
        st.markdown("**Alignment summary**")
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Aligner:** {stage.aligner or '—'}")
        c2.write(f"**Length:** {stage.alignment_length} positions")
        c3.write(f"**Sequences:** {len(stage.aligned_sequences)}")
        meta_parts = []
        if stage.completed_at:
            meta_parts.append(f"Completed: {stage.completed_at}")
        if stage.mafft_version:
            meta_parts.append(f"MAFFT version: {stage.mafft_version}")
        if meta_parts:
            st.caption("  ·  ".join(meta_parts))

        render_aligned_sequences_expander(session)

        with st.expander("Raw MAFFT output"):
            if stage.mafft_stdout_snippet:
                if stage.mafft_stdout_truncated:
                    st.warning("Output was truncated to 50 000 characters.")
                st.code(stage.mafft_stdout_snippet, language=None)
            else:
                st.write("No output captured.")

        if st.button("Reopen alignment", type="secondary"):
            st.session_state["ui_alignment_show_reopen_confirm"] = True

        if st.session_state.get("ui_alignment_show_reopen_confirm"):
            _dialog_reopen_alignment()

        # ── analysis section ──────────────────────────────────────────────────

        st.divider()
        if has_computed_profiles(session):
            st.info("Analysis profiles are computed. Go to Step 3: Analysis to view charts.")
        else:
            analysis_error = st.session_state.get("ui_alignment_analysis_error_msg")
            if analysis_error:
                st.error(f"Analysis computation failed: {analysis_error}")
                if st.button("Retry analysis", type="primary"):
                    with st.spinner("Computing profiles..."):
                        success, err_msg = compute_profiles(session)
                    if success:
                        mark_session_changed()
                        st.session_state.pop("ui_alignment_analysis_error_msg", None)
                        set_feedback("success", "Analysis profiles computed.")
                        st.switch_page("pages/3_Analysis.py")
                    else:
                        st.session_state["ui_alignment_analysis_error_msg"] = err_msg
                        st.rerun()
            else:
                if st.button("Start analysis", type="primary"):
                    with st.spinner("Computing profiles..."):
                        success, err_msg = compute_profiles(session)
                    if success:
                        mark_session_changed()
                        set_feedback("success", "Analysis profiles computed.")
                        st.switch_page("pages/3_Analysis.py")
                    else:
                        st.session_state["ui_alignment_analysis_error_msg"] = err_msg
                        st.rerun()

    # ── error view ────────────────────────────────────────────────────────────

    elif stage.status == AlignmentStatus.ERROR:
        st.error(f"Alignment failed: {stage.error_summary or 'Unknown error.'}")
        with st.expander("MAFFT output"):
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("stdout")
                if stage.mafft_stdout_snippet:
                    if stage.mafft_stdout_truncated:
                        st.warning("Truncated.")
                    st.code(stage.mafft_stdout_snippet, language=None)
                else:
                    st.write("No stdout captured.")
            with col2:
                st.subheader("stderr")
                if stage.mafft_stderr_snippet:
                    if stage.mafft_stderr_truncated:
                        st.warning("Truncated.")
                    st.code(stage.mafft_stderr_snippet, language=None)
                else:
                    st.write("No stderr captured.")

        if st.button("Retry", type="primary"):
            with st.spinner("Running MAFFT..."):
                success, err_msg = run_alignment(session)
            mark_session_changed()
            if success:
                set_feedback("success", "Alignment completed successfully.")
            else:
                set_feedback("error", f"Alignment failed: {err_msg}")
            st.rerun()

    # ── not started view ──────────────────────────────────────────────────────

    else:
        st.write("Ready to align.")
        if st.button("Start alignment", type="primary"):
            with st.spinner("Running MAFFT..."):
                success, err_msg = run_alignment(session)
            mark_session_changed()
            if success:
                set_feedback("success", "Alignment completed successfully.")
            else:
                set_feedback("error", f"Alignment failed: {err_msg}")
            st.rerun()

# ── navigation ────────────────────────────────────────────────────────────────

st.divider()
nav_prev, nav_next = st.columns(2)
with nav_prev:
    if st.button("← Step 1: Input"):
        st.switch_page("pages/1_Input.py")
with nav_next:
    if st.button("Step 3: Analysis →", disabled=not has_valid_alignment(session)):
        st.switch_page("pages/3_Analysis.py")

render_processing_history_expander(session)
