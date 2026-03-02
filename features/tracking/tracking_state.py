from __future__ import annotations

from typing_extensions import TypedDict


class TrackingState(TypedDict):
    active: bool
    camera_id: str
    subject_description: str
    user_extra_context: str
    observations: list[dict[str, object]]
    consecutive_lost_count: int
    subject_lost: bool
    subject_lost_timestamp: str
    bolo_active: bool
    bolo_text: str
    reacquired: bool
    reacquired_camera_id: str
    reacquired_frame_path: str | None
    reacquired_timestamp: str
    reacquired_confidence: str
