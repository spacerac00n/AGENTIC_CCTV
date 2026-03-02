from __future__ import annotations

from datetime import datetime, timezone

from config import CAMERA_PROFILE
from features.agents.graph import IncidentState


def enrich_context(state: IncidentState) -> dict[str, object]:
    """Attach camera metadata and a fresh timestamp."""
    stamp = datetime.now(timezone.utc).isoformat()
    return {
        "camera_profile": CAMERA_PROFILE,
        "timestamp": stamp,
        "audit_trail": state["audit_trail"] + [f"Context enriched at {stamp}"],
    }
