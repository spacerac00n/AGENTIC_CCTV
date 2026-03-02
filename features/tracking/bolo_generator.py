from __future__ import annotations

from openai import OpenAI

from config import (
    BOLO_FALLBACK_TEXT,
    BOLO_SYSTEM_PROMPT,
    BOLO_USER_PROMPT_TEMPLATE,
    OPENAI_API_KEY_2,
    TRACKING_MODEL,
)
from features.tracking.tracking_state import TrackingState


def generate_bolo(tracking_state: TrackingState) -> str:
    """Generate a structured BOLO card or return a safe fallback."""
    if not OPENAI_API_KEY_2:
        return BOLO_FALLBACK_TEXT
    prompt = BOLO_USER_PROMPT_TEMPLATE.format(
        observations=tracking_state.get("observations", []),
        subject_description=tracking_state.get("subject_description", ""),
        user_extra_context=tracking_state.get("user_extra_context", ""),
    )
    try:
        response = OpenAI(api_key=OPENAI_API_KEY_2).responses.create(
            model=TRACKING_MODEL,
            input=[
                {"role": "system", "content": BOLO_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception:
        return BOLO_FALLBACK_TEXT
    text = str(getattr(response, "output_text", "")).strip()
    return text or BOLO_FALLBACK_TEXT
