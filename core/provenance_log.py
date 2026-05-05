from __future__ import annotations

from datetime import UTC, datetime

from core.analysis_session_models import AnalysisSession, ProvenanceEvent


def append_event(
    session: AnalysisSession,
    event_type: str,
    payload: dict | None = None,
) -> None:
    event = ProvenanceEvent(
        timestamp=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        event_type=event_type,
        payload=payload or {},
    )
    session.provenance_log.append(event)
