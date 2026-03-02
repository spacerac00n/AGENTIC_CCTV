from __future__ import annotations

from uuid import uuid4

import streamlit as st

from features.agents.graph import IncidentState


def _audit_log() -> list[dict[str, object]]:
    """Return the in-session audit log store."""
    return st.session_state.setdefault("audit_log", [])


def next_case_id() -> str:
    """Return a compact case identifier."""
    return f"case-{uuid4().hex[:8]}"


def log_incident(state: IncidentState) -> dict[str, object]:
    """Store or update one incident in the shared session audit log."""
    case_id = str(state.get("case_id", "")) or next_case_id()
    camera_id = str(state.get("camera_profile", {}).get("camera_id", ""))
    trail = list(state.get("audit_trail", [])) + [f"Incident stored as {case_id}"]
    entry = {**state, "case_id": case_id, "camera_id": camera_id, "audit_trail": trail}
    record = dict(state.get("ai_incident_record", {}))
    if record:
        entry["ai_incident_record"] = {**record, "case_id": case_id}
    log = list(_audit_log())
    for index, existing in enumerate(log):
        if existing.get("case_id") == case_id:
            log[index] = entry
            break
    else:
        log.append(entry)
    st.session_state["audit_log"] = log
    return {"case_id": case_id, "audit_trail": trail}


def read_audit_log() -> list[dict[str, object]]:
    """Return a copy of the shared session audit log."""
    return list(_audit_log())


def get_audit_by_camera(camera_id: str) -> list[dict[str, object]]:
    """Return audit entries for a single camera."""
    return [entry for entry in _audit_log() if entry.get("camera_id") == camera_id]
