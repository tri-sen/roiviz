from __future__ import annotations

import uuid
from datetime import UTC, datetime

import streamlit as st

from core.analysis_session_models import (
    AlignmentStage,
    AlignmentStatus,
    AnalysisSession,
    AnalysisStage,
)
from core.constants import STANDARD_AMINO_ACIDS
from core.provenance_log import append_event


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def create_new_session() -> AnalysisSession:
    session_id = f"session_{uuid.uuid4().hex[:12]}"
    now = _utc_now()
    return AnalysisSession(id=session_id, created_at=now, updated_at=now)


def get_session() -> AnalysisSession:
    return st.session_state["session"]


_VALID_AAS: frozenset[str] = frozenset(STANDARD_AMINO_ACIDS)


def has_valid_input(session: AnalysisSession) -> bool:
    seqs = session.input_stage.selected_sequences
    if not (2 <= len(seqs) <= 6):
        return False
    names = [s.name.strip() for s in seqs]
    if len(names) != len(set(names)):
        return False
    for s in seqs:
        if not s.sequence or not all(c in _VALID_AAS for c in s.sequence):
            return False
    return True


def has_valid_alignment(session: AnalysisSession) -> bool:
    stage = session.alignment_stage
    if stage.status != AlignmentStatus.SUCCESS:
        return False
    aligned = stage.aligned_sequences
    if len(aligned) != len(session.input_stage.selected_sequences):
        return False
    if len({len(a.aligned_sequence) for a in aligned}) != 1:
        return False
    input_ids = {s.id for s in session.input_stage.selected_sequences}
    return all(a.input_sequence_id in input_ids for a in aligned)


def has_computed_profiles(session: AnalysisSession) -> bool:
    return session.analysis_stage.computed_profiles is not None


def clear_alignment_and_analysis(session: AnalysisSession) -> None:
    session.alignment_stage = AlignmentStage()
    session.analysis_stage = AnalysisStage()
    append_event(session, "downstream_state_cleared", {
        "reason": "input_changed",
        "cleared_alignment": True,
        "cleared_analysis": True,
        "cleared_annotations": True,
    })
    update_session_timestamp(session)
    mark_session_changed()


def _input_is_editing() -> bool:
    """Returns True if the user is currently editing the input stage."""
    return bool(st.session_state.get("ui_input_editing", False))


def is_stage_reachable(session: AnalysisSession, stage_key: str) -> bool:
    """Returns True if the user can navigate to this stage."""
    if stage_key == "input":
        return True
    if stage_key == "alignment":
        return has_valid_input(session) and not _input_is_editing()
    if stage_key == "analysis":
        return has_valid_alignment(session)
    return False


def is_stage_locked(session: AnalysisSession, stage_key: str) -> bool:
    if stage_key == "input":
        return has_valid_input(session) and (
            has_valid_alignment(session) or has_computed_profiles(session)
        )
    if stage_key == "alignment":
        return has_valid_alignment(session) and has_computed_profiles(session)
    return False


def is_stage_editable(session: AnalysisSession, stage_key: str) -> bool:
    return is_stage_reachable(session, stage_key) and not is_stage_locked(session, stage_key)


def get_stage_status(session: AnalysisSession, stage_key: str) -> str:
    """Returns a display status string for the workflow indicator.

    Returns one of: Not started, Incomplete, Ready, Complete, Locked, Error.
    """
    if stage_key == "input":
        seqs = session.input_stage.selected_sequences
        if len(seqs) == 0:
            return "Not started"
        if not has_valid_input(session):
            return "Incomplete"
        if has_valid_alignment(session) or has_computed_profiles(session):
            return "Locked"
        return "Ready"
    if stage_key == "alignment":
        stage = session.alignment_stage
        if stage.status == AlignmentStatus.ERROR:
            return "Error"
        if stage.status == AlignmentStatus.SUCCESS and has_valid_alignment(session):
            if has_computed_profiles(session):
                return "Locked"
            return "Complete"
        if has_valid_input(session) and not _input_is_editing():
            return "Ready"
        return "Not started"
    if stage_key == "analysis":
        if has_computed_profiles(session):
            return "Complete"
        if has_valid_alignment(session):
            return "Ready"
        return "Not started"
    return "Not started"


def update_session_timestamp(session: AnalysisSession) -> None:
    session.updated_at = _utc_now()


def mark_session_changed() -> None:
    st.session_state["ui_session_changed"] = True


def set_feedback(feedback_type: str, message: str) -> None:
    st.session_state["ui_feedback"] = {"type": feedback_type, "message": message}


def get_feedback() -> dict | None:
    return st.session_state.get("ui_feedback")


def clear_feedback() -> None:
    st.session_state.pop("ui_feedback", None)
