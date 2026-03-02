from __future__ import annotations

import json

from openai import OpenAI

from config import OPENAI_API_KEY, VISION_MODEL, VISION_SYSTEM_PROMPT, VISION_USER_PROMPT
from features.agents.graph import IncidentState

CLIENT = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
VALID_THREAT_TYPES = {"weapon", "physical_altercation", "suspicious_behaviour", "none"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_CROWD_DENSITY = {"low", "medium", "high"}
MIN_RISK_SCORE = 0.0
MAX_RISK_SCORE = 10.0


def _fallback() -> dict[str, object]:
    """Return a safe payload when detection fails."""
    return {
        "threat_detected": False,
        "threat_type": "none",
        "confidence": "low",
        "people_count": 0,
        "crowd_density": "low",
        "description": "Detection unavailable.",
    }


def _merge_api_error(existing: str, new: str) -> str:
    """Keep a clean user-facing API error note."""
    if not new:
        return existing
    if not existing or existing == new:
        return new
    return "Multiple AI stages used fallback responses."


def _safe_int(value: object, default: int = 0) -> int:
    """Convert a value to int without throwing."""
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _safe_risk_score(value: object) -> float | None:
    """Convert a model-provided risk score when available."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return min(max(score, MIN_RISK_SCORE), MAX_RISK_SCORE)


def _normalize_payload(payload: dict[str, object]) -> tuple[dict[str, object], bool]:
    """Normalize the model payload and flag incomplete values."""
    crowd_density = str(payload.get("crowd_density", "")).strip().lower()
    crowd_fallback = crowd_density not in VALID_CROWD_DENSITY
    threat_type = str(payload.get("threat_type", "none")).strip().lower()
    confidence = str(payload.get("confidence", "low")).strip().lower()
    normalized_payload = {
        "threat_detected": bool(payload.get("threat_detected", False)),
        "threat_type": threat_type if threat_type in VALID_THREAT_TYPES else "none",
        "confidence": confidence if confidence in VALID_CONFIDENCE else "low",
        "people_count": _safe_int(payload.get("people_count", 0)),
        "crowd_density": crowd_density if crowd_density in VALID_CROWD_DENSITY else "low",
        "description": str(payload.get("description", "")).strip()
        or _fallback()["description"],
    }
    risk_score = _safe_risk_score(payload.get("risk_score"))
    if risk_score is not None:
        normalized_payload["risk_score"] = risk_score
    return normalized_payload, crowd_fallback


def _vision_prompt(camera_profile: dict[str, object]) -> str:
    """Build the location-aware user prompt for the vision model."""
    camera_id = str(camera_profile.get("camera_id", "")).strip()
    location_name = str(camera_profile.get("location_name", "")).strip()
    zone_type = str(camera_profile.get("zone_type", "")).strip()
    return (
        f"{VISION_USER_PROMPT} Camera ID: {camera_id or 'unknown'}. "
        f"Location: {location_name or 'unknown'}. "
        f"Zone type: {zone_type or 'unknown'}."
    )


def detect_frame(frame_b64: str, camera_profile: dict[str, object]) -> dict[str, object]:
    """Analyze a base64 frame with the configured vision model."""
    fallback = _fallback()
    if CLIENT is None:
        return {
            "payload": fallback,
            "used_fallback": True,
            "api_error_message": "Vision model unavailable; fallback response used.",
            "stage_status": "fallback",
        }
    try:
        response = CLIENT.responses.create(
            model=VISION_MODEL,
            input=[
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": _vision_prompt(camera_profile)},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{frame_b64}",
                        },
                    ],
                },
            ],
        )
    except Exception as exc:
        print(f"API error occurred: {exc}")
        return {
            "payload": fallback,
            "used_fallback": True,
            "api_error_message": "Vision API request failed; fallback response used.",
            "stage_status": "fallback",
        }
    try:
        payload = json.loads(getattr(response, "output_text", ""))
    except json.JSONDecodeError:
        payload = fallback
        return {
            "payload": payload,
            "used_fallback": True,
            "api_error_message": "",
            "stage_status": "fallback",
        }
    if not isinstance(payload, dict):
        return {
            "payload": fallback,
            "used_fallback": True,
            "api_error_message": "",
            "stage_status": "fallback",
        }
    normalized_payload, crowd_fallback = _normalize_payload(payload)
    return {
        "payload": normalized_payload,
        "used_fallback": crowd_fallback,
        "api_error_message": "",
        "stage_status": "fallback" if crowd_fallback else "completed",
    }


def vlm_detect(state: IncidentState) -> dict[str, object]:
    """Run detection and map the result into shared graph state."""
    result = detect_frame(state["frame_b64"], state.get("camera_profile", {}))
    payload = dict(result["payload"])
    audit_note = (
        "Vision fallback used"
        if result["stage_status"] == "fallback"
        else "Vision analysis complete"
    )
    return {
        "threat_detected": bool(payload.get("threat_detected", False)),
        "threat_type": str(payload.get("threat_type", "none")),
        "confidence": str(payload.get("confidence", "low")),
        "people_count": int(payload.get("people_count", 0)),
        "crowd_density": str(payload.get("crowd_density", "low")),
        "frame_description": str(payload.get("description", "")),
        "detection_output": payload,
        "detection_status": str(result["stage_status"]),
        "api_error_message": _merge_api_error(
            str(state.get("api_error_message", "")),
            str(result["api_error_message"]),
        ),
        "used_fallback": bool(state.get("used_fallback", False))
        or bool(result["used_fallback"]),
        "audit_trail": state["audit_trail"] + [audit_note],
    }
