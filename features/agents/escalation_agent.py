from __future__ import annotations

import json

from langchain_openai import ChatOpenAI

from config import AGENT_MODEL, ESCALATION_SYSTEM_PROMPT, OPENAI_API_KEY
from features.agents.graph import IncidentState

MODEL = (
    ChatOpenAI(model=AGENT_MODEL, api_key=OPENAI_API_KEY, temperature=0)
    if OPENAI_API_KEY
    else None
)


def _fallback(state: IncidentState) -> dict[str, object]:
    """Return a deterministic summary when the LLM is unavailable."""
    summary = f"{state['threat_type'].replace('_', ' ')} at {state['timestamp']}."
    action = "Monitor on mode 1-2 or dispatch responders immediately for mode 3."
    return {"incident_summary": summary, "recommended_action": action}


def _prompt(state: IncidentState) -> str:
    """Build the escalation prompt from the shared incident state."""
    return (
        "Return JSON with incident_summary and recommended_action for this "
        f"threat={state['threat_type']}, confidence={state['confidence']}, "
        f"risk_score={state['risk_score']}, escalation_mode={state['escalation_mode']}, "
        f"location={state['camera_profile'].get('location_name', '')}, "
        f"description={state['frame_description']}."
    )


def _merge_api_error(existing: str, new: str) -> str:
    """Keep a clean user-facing API error note."""
    if not new:
        return existing
    if not existing or existing == new:
        return new
    return "Multiple AI stages used fallback responses."


def escalate_incident(state: IncidentState) -> dict[str, object]:
    """Generate the incident summary and recommended action."""
    fallback = _fallback(state)
    if MODEL is None:
        payload = fallback
        stage_status = "fallback"
        api_error_message = "Escalation model unavailable; fallback response used."
        audit_note = "Escalation fallback used"
    else:
        try:
            message = MODEL.invoke(
                [("system", ESCALATION_SYSTEM_PROMPT), ("human", _prompt(state))]
            )
        except Exception as exc:
            print(f"API error occurred: {exc}")
            payload = fallback
            stage_status = "fallback"
            api_error_message = "Escalation API request failed; fallback response used."
            audit_note = "Escalation fallback used"
        else:
            try:
                payload = json.loads(str(message.content))
            except json.JSONDecodeError:
                payload = fallback
                stage_status = "fallback"
                api_error_message = ""
                audit_note = "Escalation fallback used"
            else:
                if not isinstance(payload, dict):
                    payload = fallback
                    stage_status = "fallback"
                    api_error_message = ""
                    audit_note = "Escalation fallback used"
                else:
                    stage_status = "completed"
                    api_error_message = ""
                    audit_note = "Escalation summary prepared"
    return {
        "incident_summary": str(payload.get("incident_summary", fallback["incident_summary"])),
        "recommended_action": str(
            payload.get("recommended_action", fallback["recommended_action"])
        ),
        "escalation_output": {
            "incident_summary": str(
                payload.get("incident_summary", fallback["incident_summary"])
            ),
            "recommended_action": str(
                payload.get("recommended_action", fallback["recommended_action"])
            ),
        },
        "escalation_status": stage_status,
        "api_error_message": _merge_api_error(
            str(state.get("api_error_message", "")),
            api_error_message,
        ),
        "used_fallback": bool(state.get("used_fallback", False))
        or stage_status == "fallback",
        "audit_trail": state["audit_trail"] + [audit_note],
    }
