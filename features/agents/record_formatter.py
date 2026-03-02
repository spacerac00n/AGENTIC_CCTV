from __future__ import annotations

from typing import TypedDict

from config import COLOR_CRITERIA
from features.agents.graph import IncidentState


class AIStageRecord(TypedDict):
    stage_name: str
    status: str
    summary: str
    raw_json: dict[str, object] | None


class AIIncidentRecord(TypedDict):
    case_id: str
    timestamp: str
    camera: dict[str, str]
    status: dict[str, object]
    executive_summary: str
    operational_impact: str
    key_details: dict[str, object]
    decision_path: list[AIStageRecord]
    structured_output: dict[str, object]
    system_status: dict[str, object]


def _humanize(text: str) -> str:
    """Convert snake_case values into user-facing text."""
    cleaned = text.replace("_", " ").strip()
    return cleaned or "none"


def _normalized_dispatch_status(state: IncidentState) -> str:
    """Return a consistent status for display and storage."""
    status = str(state.get("dispatch_status", "pending"))
    if status == "pending" and state.get("escalation_mode", 1) < 3:
        return "monitoring"
    return status


def _status_badge(state: IncidentState) -> str:
    """Return the primary status badge label."""
    return str(state.get("threat_label", COLOR_CRITERIA["green"]["label"]))


def _system_status(state: IncidentState) -> dict[str, object]:
    """Return fallback and API status metadata."""
    api_error = str(state.get("api_error_message", "")).strip()
    return {
        "used_fallback": bool(state.get("used_fallback", False)),
        "api_error": api_error or None,
    }


def _executive_summary(state: IncidentState) -> str:
    """Create a short operator-facing summary."""
    if str(state.get("detection_status", "completed")) == "fallback":
        return (
            "Primary vision analysis is unavailable, so the system is using a "
            "fallback assessment. Operators should review this frame manually while "
            "situational coverage is maintained."
        )
    threat_label = str(state.get("threat_label", COLOR_CRITERIA["green"]["label"]))
    threat_color = str(state.get("threat_color", "green"))
    if threat_color == "green":
        return (
            "The scene is classified as Normal. Routine monitoring continues to "
            "support calm operations and steady situational awareness."
        )
    threat = _humanize(str(state.get("threat_type", "none")))
    confidence = str(state.get("confidence", "low"))
    risk_score = float(state.get("risk_score", 0.0))
    if threat_color == "yellow":
        return (
            f"The scene is classified as {threat_label} at {risk_score:.1f}. "
            f"A potential {threat} concern was detected with {confidence} confidence, "
            "so operators should continue close monitoring."
        )
    if threat_color == "orange":
        return (
            f"The scene is classified as {threat_label} at {risk_score:.1f}. "
            f"A potential {threat} concern was detected with {confidence} confidence, "
            "so the incident needs elevated operator attention."
        )
    return (
        f"The scene is classified as {threat_label} at {risk_score:.1f}. "
        f"A potential {threat} threat was detected with {confidence} confidence, "
        "so immediate coordinated response is required."
    )


def _operational_impact(state: IncidentState) -> str:
    """Connect the outcome to the operator's decision goals."""
    if not state.get("threat_detected", False):
        return (
            "This record supports continuous situational awareness and informed "
            "decision-making even when no threat is detected."
        )
    if int(state.get("escalation_mode", 1)) == 3:
        return (
            "This record strengthens early detection and coordinated response by "
            "giving operators a clear, high-priority view of the incident."
        )
    return (
        "This record improves situational awareness and informed decision-making "
        "by surfacing key risk cues before the situation escalates."
    )


def _detection_stage(state: IncidentState) -> AIStageRecord:
    """Build the detection timeline item."""
    payload = dict(state.get("detection_output", {}))
    status = str(state.get("detection_status", "completed"))
    description = str(payload.get("description", "")).strip()
    if status == "fallback":
        summary = (
            "The vision stage used a fallback assessment because the primary "
            "analysis could not be completed."
        )
    elif state.get("threat_detected", False):
        summary = (
            f"The vision stage flagged {_humanize(str(state.get('threat_type', 'none')))} "
            f"with {state.get('confidence', 'low')} confidence."
        )
    else:
        summary = "The vision stage detected no immediate threat in the frame."
    if description:
        summary = f"{summary} {description}"
    return {
        "stage_name": "Detection",
        "status": status,
        "summary": summary,
        "raw_json": payload or None,
    }


def _risk_stage(state: IncidentState) -> AIStageRecord:
    """Build the risk-assessment timeline item."""
    payload = dict(state.get("risk_output", {}))
    status = str(state.get("risk_status", "completed"))
    mode = int(state.get("escalation_mode", 1))
    label = str(state.get("threat_label", COLOR_CRITERIA["green"]["label"]))
    color = str(state.get("threat_color", "green"))
    risk_score = float(state.get("risk_score", 0.0))
    reasoning = str(payload.get("reasoning", "")).strip()
    source = _humanize(str(payload.get("source", "llm")))
    if status == "fallback":
        summary = (
            f"The risk stage used a {source} score of {risk_score:.1f}, which maps "
            f"to {label} ({color}) and mode {mode}."
        )
    else:
        summary = (
            f"The risk LLM scored the scene at {risk_score:.1f}, which maps to "
            f"{label} ({color}) and mode {mode}."
        )
    if reasoning:
        summary = f"{summary} {reasoning}"
    return {
        "stage_name": "Risk Assessment",
        "status": status,
        "summary": summary,
        "raw_json": payload or None,
    }


def _escalation_stage(state: IncidentState) -> AIStageRecord:
    """Build the escalation timeline item."""
    payload = dict(state.get("escalation_output", {}))
    status = str(state.get("escalation_status", "completed"))
    incident_summary = str(payload.get("incident_summary", "")).strip()
    recommended_action = str(payload.get("recommended_action", "")).strip()
    if status == "fallback":
        summary = "The escalation stage used a fallback recommendation for operator review."
    else:
        summary = "The escalation stage prepared the incident framing and response guidance."
    if incident_summary:
        summary = f"{summary} {incident_summary}"
    if recommended_action:
        summary = f"{summary} Action: {recommended_action}"
    return {
        "stage_name": "Escalation",
        "status": status,
        "summary": summary,
        "raw_json": payload or None,
    }


def _dispatch_stage(state: IncidentState, dispatch_status: str) -> AIStageRecord:
    """Build the dispatch timeline item."""
    payload = dict(state.get("dispatch_output", {}))
    if not payload:
        payload = {"dispatch_status": dispatch_status}
    if dispatch_status == "awaiting_confirmation":
        return {
            "stage_name": "Dispatch",
            "status": "waiting",
            "summary": "Dispatch is paused pending operator confirmation.",
            "raw_json": payload,
        }
    if dispatch_status == "dispatched":
        return {
            "stage_name": "Dispatch",
            "status": "completed",
            "summary": "Dispatch has been sent to operators for coordinated response.",
            "raw_json": payload,
        }
    return {
        "stage_name": "Dispatch",
        "status": "completed",
        "summary": "No dispatch was required and the incident remains under monitoring.",
        "raw_json": payload,
    }


def _structured_output(
    state: IncidentState,
    dispatch_status: str,
    system_status: dict[str, object],
) -> dict[str, object]:
    """Return the structured JSON bundle exposed in the UI."""
    detection_output = dict(state.get("detection_output", {}))
    detection_output.pop("people_count", None)
    detection_output.pop("crowd_density", None)
    risk_output = dict(state.get("risk_output", {}))
    risk_output.pop("crowd_density", None)
    escalation_output = dict(state.get("escalation_output", {}))
    dispatch_output = dict(state.get("dispatch_output", {})) or {
        "dispatch_status": dispatch_status
    }
    return {
        "final_assessment": {
            "threat_detected": bool(state.get("threat_detected", False)),
            "threat_type": str(state.get("threat_type", "none")),
            "confidence": str(state.get("confidence", "low")),
            "risk_score": float(state.get("risk_score", 0.0)),
            "threat_color": str(state.get("threat_color", "green")),
            "threat_label": str(
                state.get("threat_label", COLOR_CRITERIA["green"]["label"])
            ),
            "escalation_mode": int(state.get("escalation_mode", 1)),
            "recommended_action": str(state.get("recommended_action", "")),
        },
        "stage_outputs": {
            "detection": detection_output,
            "risk_assessment": risk_output,
            "escalation": escalation_output,
            "dispatch": dispatch_output,
        },
        "system_status": system_status,
    }


def build_ai_incident_record(state: IncidentState) -> AIIncidentRecord:
    """Return a normalized user-facing incident record."""
    dispatch_status = _normalized_dispatch_status(state)
    system_status = _system_status(state)
    structured_output = _structured_output(state, dispatch_status, system_status)
    return {
        "case_id": str(state.get("case_id", "")),
        "timestamp": str(state.get("timestamp", "")),
        "camera": {
            "camera_id": str(state.get("camera_profile", {}).get("camera_id", "")),
            "location_name": str(
                state.get("camera_profile", {}).get("location_name", "")
            ),
        },
        "status": {
            "status_badge": _status_badge(state),
            "threat_color": str(state.get("threat_color", "green")),
            "threat_label": str(
                state.get("threat_label", COLOR_CRITERIA["green"]["label"])
            ),
            "escalation_mode": int(state.get("escalation_mode", 1)),
            "dispatch_status": dispatch_status,
        },
        "executive_summary": _executive_summary(state),
        "operational_impact": _operational_impact(state),
        "key_details": {
            "threat_detected": bool(state.get("threat_detected", False)),
            "threat_type": str(state.get("threat_type", "none")),
            "confidence": str(state.get("confidence", "low")),
            "risk_score": float(state.get("risk_score", 0.0)),
            "recommended_action": str(state.get("recommended_action", "")),
            "dispatch_status": dispatch_status,
        },
        "decision_path": [
            _detection_stage(state),
            _risk_stage(state),
            _escalation_stage(state),
            _dispatch_stage(state, dispatch_status),
        ],
        "structured_output": structured_output,
        "system_status": system_status,
    }


def format_incident_record(state: IncidentState) -> dict[str, object]:
    """Attach the normalized incident record to shared state."""
    dispatch_status = _normalized_dispatch_status(state)
    record = build_ai_incident_record({**state, "dispatch_status": dispatch_status})
    return {
        "dispatch_status": dispatch_status,
        "dispatch_output": dict(state.get("dispatch_output", {}))
        or {"dispatch_status": dispatch_status},
        "ai_incident_record": record,
        "audit_trail": state["audit_trail"] + ["AI decision record prepared"],
    }
