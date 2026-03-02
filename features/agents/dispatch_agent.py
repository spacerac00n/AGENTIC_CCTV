from __future__ import annotations

import base64
from pathlib import Path

from config import DATA_DIR
from features.agents.graph import IncidentState


def save_frame_snapshot(state: dict[str, object]) -> str:
    """Persist a frame snapshot to disk and return its path."""
    frame_b64 = str(state.get("frame_b64", "")).strip()
    if not frame_b64:
        return str(state.get("frame_path", ""))
    camera = str(state.get("camera_profile", {}).get("camera_id", "camera")) or "camera"
    case_id = str(state.get("case_id", "frame")) or "frame"
    path = Path(DATA_DIR) / f"{camera}_{case_id}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(base64.b64decode(frame_b64))
    except Exception:
        return str(state.get("frame_path", ""))
    return str(path)


def dispatch_incident(state: IncidentState) -> dict[str, object]:
    """Update dispatch status and save a snapshot when dispatch is finalised."""
    approved = bool(state["human_approved"])
    status = "dispatched" if approved else "awaiting_confirmation"
    note = "Dispatch sent to operators" if approved else "Dispatch paused for approval"
    result: dict[str, object] = {
        "dispatch_status": status,
        "dispatch_output": {"dispatch_status": status},
        "audit_trail": state["audit_trail"] + [note],
    }
    if approved:
        frame_path = save_frame_snapshot(state)
        if frame_path:
            result["frame_path"] = frame_path
            result["dispatch_output"] = {"dispatch_status": status, "frame_path": frame_path}
    return result
