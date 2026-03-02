from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st
from openai import OpenAI

from config import OPENAI_API_KEY_2, TRACKING_PROMPT_TEMPLATE, TRACKING_VLM_MODEL
from features.dashboard.police_chat import notify_tracker_match
from features.tracking.tracking_state import TrackingState
from features.vision_fallback import request_vision_json

CLIENT = OpenAI(api_key=OPENAI_API_KEY_2) if OPENAI_API_KEY_2 else None


def _as_visible(value: object) -> bool:
    """Coerce model output into a visibility boolean."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "visible", "detected", "1"}


def _observe(frame_b64: str, prompt: str) -> dict[str, object]:
    """Return one Agent 2 VLM observation or a safe fallback."""
    if not frame_b64:
        return {
            "subject_visible": False,
            "last_position": "",
            "confidence": "low",
            "notes": "",
        }
    payload, source, failure_reason = request_vision_json(
        client=CLIENT,
        model=TRACKING_VLM_MODEL,
        system_prompt=prompt,
        user_prompt="Analyze this frame.",
        frame_b64=frame_b64,
    )
    if not payload:
        return {
            "subject_visible": False,
            "last_position": "",
            "confidence": "low",
            "notes": {
                "primary_unavailable": "Tracking vision model unavailable.",
                "primary_request_failed": "Tracking vision request failed.",
                "primary_invalid_response": "Tracking vision returned invalid output.",
            }.get(failure_reason, ""),
        }
    if source == "ollama":
        payload = {
            **payload,
            "notes": str(payload.get("notes", "")).strip()
            or "Tracking observation generated with Ollama fallback.",
        }
    return payload if isinstance(payload, dict) else {"subject_visible": False}


def start_tracking(initial_state: TrackingState) -> None:
    """Activate the Track Card state for the UI."""
    st.session_state["tracking"] = dict(initial_state)


def check_tracking_match(
    frame_b64: str,
    camera_id: str,
    frame_index: int,
    source_offset_seconds: float,
    fallback_detected: bool = False,
    fallback_description: str = "",
) -> None:
    """Run the Camera 2 tracking check and append positive sightings."""
    tracking = dict(st.session_state.get("tracking", {}))
    if not tracking or not tracking.get("active"):
        return
    if camera_id != str(tracking.get("search_camera_id", "")):
        return
    prompt = TRACKING_PROMPT_TEMPLATE.format(
        subject_description=tracking.get("subject_description", ""),
        user_extra_context=tracking.get("user_extra_context", ""),
    )
    observation = _observe(frame_b64, prompt)
    subject_visible = _as_visible(observation.get("subject_visible"))
    if not subject_visible and fallback_detected:
        observation = {
            **observation,
            "subject_visible": True,
            "last_position": str(observation.get("last_position", "")).strip() or "Visible in Camera 2 frame",
            "confidence": str(observation.get("confidence", "")).strip() or "low",
            "notes": str(observation.get("notes", "")).strip()
            or (
                "Tracking fallback used from Camera 2 threat detection."
                + (f" {fallback_description}" if fallback_description else "")
            ),
        }
        subject_visible = True
    if not subject_visible:
        return
    seen_at = datetime.now(timezone.utc).isoformat()
    sighting = {
        "camera_id": camera_id,
        "last_seen_camera": camera_id,
        "frame_index": frame_index,
        "frame_b64": frame_b64,
        "source_offset_seconds": source_offset_seconds,
        "timestamp": seen_at,
        "last_seen_timestamp": seen_at,
        "last_position": str(observation.get("last_position", "")),
        "confidence": str(observation.get("confidence", "low")),
        "notes": str(observation.get("notes", "")),
    }
    tracking["sightings"] = list(tracking.get("sightings", [])) + [sighting]
    tracking["last_sighting"] = sighting
    st.session_state["tracking"] = tracking
    notify_tracker_match(
        camera_id,
        frame_index,
        sighting.get("confidence", "low"),
        str(tracking.get("threat_type", "unknown")),
    )
