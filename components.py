"""Presentational components for UI pages."""
from __future__ import annotations

import streamlit as st


def render_processing_history_expander(session: object | None) -> None:
    if not st.session_state.get("show_processing_history", False):
        return
    if session is None:
        return
    with st.expander("Processing history"):
        st.caption(
            "This history records analysis-relevant workflow events. "
            "It is not a debug log or full audit log."
        )
        log = list(reversed(session.provenance_log))
        if not log:
            st.write("No processing history recorded yet.")
        else:
            for event in log:
                st.write(f"**{event.timestamp} — {event.event_type}**")
                st.json(event.payload)


_BADGE_COLORS = {
    "Ready": "green",
    "Complete": "green",
    "Locked": "green",
    "Not started": "gray",
    "Incomplete": "orange",
    "Error": "red",
}


def render_pipeline_navigator(session: object, current_stage: str = "") -> None:
    from core.state import get_stage_status, is_stage_reachable

    stages = [
        ("Input", "input", "pages/1_Input.py"),
        ("Alignment", "alignment", "pages/2_Alignment.py"),
        ("Analysis", "analysis", "pages/3_Analysis.py"),
    ]

    cols = st.columns(3)
    for i, (name, key, path) in enumerate(stages):
        is_current = key == current_stage
        status = get_stage_status(session, key)
        reachable = is_stage_reachable(session, key)
        with cols[i]:
            st.markdown(f"**{name}**" if is_current else name)
            if is_current:
                st.caption("Current page")
            st.badge(status, color=_BADGE_COLORS.get(status, "gray"))
            if not is_current and reachable:
                if st.button(
                    f"Go to {name}",
                    key=f"_nav_{key}",
                    use_container_width=True,
                ):
                    st.switch_page(path)

    st.divider()


_STAGE_DISPLAY_NAMES = {
    "input": "Input",
    "alignment": "Alignment",
    "analysis": "Analysis",
}


def _workflow_box_content(
    session: object, stage_key: str, status: str
) -> tuple[str, str, str | None, str | None]:
    """Returns (description, state_summary, next_action, locked_note)."""
    if stage_key == "input":
        desc = "Select 2–6 protein sequences for alignment."
        seqs = session.input_stage.selected_sequences
        n = len(seqs)
        if status == "Not started":
            return desc, "No sequences selected yet.", "Add at least 2 sequences using the tabs below.", None
        if status == "Incomplete":
            if n == 1:
                summary = "1 sequence selected — at least 1 more required."
            else:
                summary = f"{n} sequences selected — not all are valid."
            return desc, summary, "Add or fix sequences to reach 2 valid selections.", None
        if status == "Ready":
            return desc, f"{n} sequences selected and valid.", "Continue to Alignment.", None
        return desc, f"{n} sequences committed.", None, (
            "A valid alignment or analysis data exists. "
            "Editing will delete downstream results."
        )

    if stage_key == "alignment":
        desc = "Align selected sequences using MAFFT (Automatic mode)."
        if status == "Not started":
            return desc, "Input stage not complete.", "Go to Input and add at least 2 valid sequences.", None
        if status == "Ready":
            n = len(session.input_stage.selected_sequences)
            return desc, f"{n} sequences ready to align.", "Run MAFFT alignment.", None
        stage = session.alignment_stage
        if status in ("Complete", "Locked"):
            summary = (
                f"Alignment complete: {len(stage.aligned_sequences)} sequences, "
                f"{stage.alignment_length} positions."
            )
            if status == "Locked":
                return desc, summary, None, (
                    "Analysis profiles exist. "
                    "Rerunning alignment will delete analysis results."
                )
            return desc, summary, "Compute analysis profiles to continue.", None
        if status == "Error":
            err = stage.error_summary or "Unknown error."
            return desc, f"Alignment failed: {err}", "Check MAFFT availability and retry.", None
        return desc, "Alignment not run.", None, None

    if stage_key == "analysis":
        desc = "Compute pairwise metric differences and composition from aligned positions."
        if status == "Not started":
            return desc, "No valid alignment available.", "Complete Input and Alignment steps first.", None
        if status == "Ready":
            stage = session.alignment_stage
            n = len(stage.aligned_sequences)
            length = stage.alignment_length or 0
            return desc, f"Valid alignment available: {n} sequences, {length} positions.", "Compute analysis profiles.", None
        if status == "Complete":
            profiles = session.analysis_stage.computed_profiles
            if profiles:
                n_pairs = len(profiles.alignment_pairs)
                length = profiles.alignment_length
                return desc, f"Analysis complete: {n_pairs} pairs, {length} positions.", "View charts and annotations below.", None
            return desc, "Analysis complete.", "View charts and annotations below.", None
        return desc, "Analysis status unknown.", None, None

    return "", "Status unavailable.", None, None


_SEQ_WRAP_WIDTH = 60


def _wrap_seq(seq: str) -> str:
    return "\n".join(seq[i : i + _SEQ_WRAP_WIDTH] for i in range(0, len(seq), _SEQ_WRAP_WIDTH))


def render_selected_sequences_expander(session: object) -> None:
    """Shows selected input sequences in a collapsed read-only expander."""
    seqs = session.input_stage.selected_sequences
    with st.expander("Selected input sequences", expanded=False):
        if not seqs:
            st.caption("No sequences selected.")
            return
        for seq in seqs:
            st.code(
                f">{seq.name}  [{len(seq.sequence)} aa]\n{_wrap_seq(seq.sequence)}",
                language=None,
            )


def render_aligned_sequences_expander(session: object) -> None:
    """Shows aligned sequences in a collapsed read-only expander.

    Only call when has_valid_alignment(session) is True.
    """
    aligned = session.alignment_stage.aligned_sequences
    with st.expander("Aligned sequences", expanded=False):
        for seq in aligned:
            st.code(
                f">{seq.name}  [{len(seq.aligned_sequence)} positions]\n{_wrap_seq(seq.aligned_sequence)}",
                language=None,
            )


def render_workflow_box(session: object, stage_key: str) -> None:
    """Renders a compact workflow status box for the given stage."""
    from core.state import get_stage_status

    status = get_stage_status(session, stage_key)
    color = _BADGE_COLORS.get(status, "gray")
    stage_name = _STAGE_DISPLAY_NAMES.get(stage_key, stage_key.title())
    description, state_summary, next_action, locked_note = _workflow_box_content(
        session, stage_key, status
    )

    with st.container(border=True):
        col_title, col_badge = st.columns([4, 1])
        with col_title:
            st.markdown(f"**{stage_name}**")
            st.caption(description)
        with col_badge:
            st.badge(status, color=color)
        st.write(state_summary)
        if locked_note:
            st.caption(f"Read-only: {locked_note}")
        elif next_action:
            st.caption(f"Next: {next_action}")
