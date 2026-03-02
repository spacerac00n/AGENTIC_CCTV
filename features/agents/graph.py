from __future__ import annotations

from typing import Any, Literal

from langgraph.checkpoint.memory import InMemorySaver as MemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class IncidentState(TypedDict):
    case_id: str
    camera_profile: dict[str, object]
    timestamp: str
    frame_index: int
    source_offset_seconds: float
    frame_b64: str
    frame_description: str
    threat_detected: bool
    threat_type: str
    confidence: str
    people_count: int
    crowd_density: str
    risk_score: float
    threat_color: str
    threat_label: str
    escalation_mode: int
    incident_summary: str
    recommended_action: str
    human_approved: bool
    dispatch_status: str
    detection_output: dict[str, object]
    risk_output: dict[str, object]
    escalation_output: dict[str, object]
    dispatch_output: dict[str, object]
    ai_incident_record: dict[str, object]
    api_error_message: str
    used_fallback: bool
    detection_status: str
    risk_status: str
    escalation_status: str
    audit_trail: list[str]


CHECKPOINTER = MemorySaver()


def default_state() -> IncidentState:
    """Return a blank incident state."""
    return {
        "case_id": "",
        "camera_profile": {},
        "timestamp": "",
        "frame_index": 0,
        "source_offset_seconds": 0.0,
        "frame_b64": "",
        "frame_description": "",
        "threat_detected": False,
        "threat_type": "none",
        "confidence": "low",
        "people_count": 0,
        "crowd_density": "low",
        "risk_score": 0.0,
        "threat_color": "green",
        "threat_label": "Normal",
        "escalation_mode": 1,
        "incident_summary": "",
        "recommended_action": "",
        "human_approved": False,
        "dispatch_status": "pending",
        "detection_output": {},
        "risk_output": {},
        "escalation_output": {},
        "dispatch_output": {},
        "ai_incident_record": {},
        "api_error_message": "",
        "used_fallback": False,
        "detection_status": "completed",
        "risk_status": "completed",
        "escalation_status": "completed",
        "audit_trail": [],
    }


def _route_dispatch(state: IncidentState) -> Literal["dispatch_agent", "record_formatter"]:
    """Send only mode-3 incidents through the dispatch node."""
    return "dispatch_agent" if state["escalation_mode"] == 3 else "record_formatter"


def build_graph(use_interrupt: bool = False) -> Any:
    """Compile the incident workflow graph."""
    from features.agents.context_enricher import enrich_context
    from features.agents.dispatch_agent import dispatch_incident
    from features.agents.escalation_agent import escalate_incident
    from features.agents.record_formatter import format_incident_record
    from features.audit.audit_logger import log_incident
    from features.detection.vlm_detector import vlm_detect
    from features.risk.risk_scorer import score_risk

    graph = StateGraph(IncidentState)
    graph.add_node("context_enricher", enrich_context)
    graph.add_node("vlm_detect", vlm_detect)
    graph.add_node("risk_score", score_risk)
    graph.add_node("escalation_agent", escalate_incident)
    graph.add_node("dispatch_agent", dispatch_incident)
    graph.add_node("record_formatter", format_incident_record)
    graph.add_node("audit_logger", log_incident)
    graph.add_edge(START, "context_enricher")
    graph.add_edge("context_enricher", "vlm_detect")
    graph.add_edge("vlm_detect", "risk_score")
    graph.add_edge("risk_score", "escalation_agent")
    graph.add_conditional_edges("escalation_agent", _route_dispatch)
    graph.add_edge("dispatch_agent", "record_formatter")
    graph.add_edge("record_formatter", "audit_logger")
    graph.add_edge("audit_logger", END)
    if use_interrupt:
        return graph.compile(
            checkpointer=CHECKPOINTER,
            interrupt_before=["dispatch_agent"],
        )
    return graph.compile(checkpointer=CHECKPOINTER)
