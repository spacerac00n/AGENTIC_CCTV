from __future__ import annotations

import json

from openai import OpenAI

from config import (
    COLOR_CRITERIA,
    COLOR_TO_ESCALATION_MODE,
    OPENAI_API_KEY,
    RISK_SYSTEM_PROMPT,
    RISK_USER_PROMPT,
    THREAT_COLOR_ORDER,
    VISION_MODEL,
)
from features.agents.graph import IncidentState

CLIENT = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
MIN_RISK_SCORE = 0.0
MAX_RISK_SCORE = 10.0


def _merge_api_error(existing: str, new: str) -> str:
    """Keep a clean user-facing API error note."""
    if not new:
        return existing
    if not existing or existing == new:
        return new
    return "Multiple AI stages used fallback responses."


def _normalize_risk_score(value: object) -> float | None:
    """Convert and clamp a model-provided score."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return min(max(score, MIN_RISK_SCORE), MAX_RISK_SCORE)


def _score_to_color(score: float) -> str:
    """Map a normalized risk score to a configured color band."""
    for color in THREAT_COLOR_ORDER:
        _, risk_max = COLOR_CRITERIA[color]["risk_range"]
        if score <= float(risk_max):
            return color
    return THREAT_COLOR_ORDER[-1]


def _risk_prompt(state: IncidentState) -> str:
    """Build the user prompt for the risk model."""
    camera_profile = dict(state.get("camera_profile", {}))
    return (
        f"{RISK_USER_PROMPT} Camera ID: {camera_profile.get('camera_id', 'unknown')}. "
        f"Location: {camera_profile.get('location_name', 'unknown')}. "
        f"Zone type: {camera_profile.get('zone_type', 'unknown')}. "
        f"Detection context: threat_detected={state.get('threat_detected', False)}, "
        f"threat_type={state.get('threat_type', 'none')}, "
        f"confidence={state.get('confidence', 'low')}, "
        f"people_count={state.get('people_count', 0)}, "
        f"crowd_density={state.get('crowd_density', 'low')}, "
        f"description={state.get('frame_description', '')}."
    )


def _request_risk_score(state: IncidentState) -> tuple[dict[str, object], str, str]:
    """Call the model for a risk score and return payload, status, and api error."""
    if CLIENT is None:
        return {}, "fallback", "Risk model unavailable; fallback response used."
    try:
        response = CLIENT.responses.create(
            model=VISION_MODEL,
            input=[
                {"role": "system", "content": RISK_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": _risk_prompt(state)},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{state['frame_b64']}",
                        },
                    ],
                },
            ],
        )
    except Exception as exc:
        print(f"API error occurred: {exc}")
        return {}, "fallback", "Risk API request failed; fallback response used."
    try:
        payload = json.loads(getattr(response, "output_text", ""))
    except json.JSONDecodeError:
        return {}, "fallback", ""
    if not isinstance(payload, dict):
        return {}, "fallback", ""
    return payload, "completed", ""


def _fallback_score(state: IncidentState) -> tuple[float, str, str]:
    """Return a deterministic fallback score when the risk model cannot respond."""
    detection_payload = dict(state.get("detection_output", {}))
    detected_score = _normalize_risk_score(detection_payload.get("risk_score"))
    if detected_score is not None:
        return (
            detected_score,
            "Preserved the detector-provided score because the dedicated risk model did not complete.",
            "detection_fallback",
        )
    return (
        0.0,
        "Risk score defaulted to 0.0 because no LLM score was available.",
        "default_fallback",
    )


def score_risk(state: IncidentState) -> dict[str, object]:
    """Score risk with the LLM, then map the score into color and escalation mode."""
    payload, stage_status, api_error_message = _request_risk_score(state)
    reasoning = str(payload.get("reasoning", "")).strip()
    risk_score = _normalize_risk_score(payload.get("risk_score"))
    source = "llm"
    if risk_score is None:
        risk_score, fallback_reasoning, source = _fallback_score(state)
        if not reasoning:
            reasoning = fallback_reasoning
        stage_status = "fallback"
    color = _score_to_color(risk_score)
    label = str(COLOR_CRITERIA[color]["label"])
    mode = int(COLOR_TO_ESCALATION_MODE[color])
    audit_note = (
        f"LLM risk score recorded at {risk_score:.1f} ({label}/{color})"
        if stage_status == "completed"
        else f"Fallback risk score recorded at {risk_score:.1f} ({label}/{color})"
    )
    return {
        "risk_score": risk_score,
        "threat_color": color,
        "threat_label": label,
        "escalation_mode": mode,
        "risk_output": {
            "risk_score": risk_score,
            "threat_color": color,
            "threat_label": label,
            "escalation_mode": mode,
            "risk_range": list(COLOR_CRITERIA[color]["risk_range"]),
            "reasoning": reasoning,
            "source": source,
        },
        "risk_status": stage_status,
        "api_error_message": _merge_api_error(
            str(state.get("api_error_message", "")),
            api_error_message,
        ),
        "used_fallback": bool(state.get("used_fallback", False))
        or stage_status == "fallback",
        "audit_trail": state["audit_trail"] + [audit_note],
    }
