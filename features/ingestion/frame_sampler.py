from __future__ import annotations

import base64
from collections.abc import Iterator
from typing import Any

import cv2

from config import FRAME_INTERVAL_SECONDS, VIDEO_PATH


def _encode_frame(frame: Any) -> str:
    """Return a JPEG frame encoded as base64."""
    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        return ""
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def sample_frames() -> Iterator[dict[str, object]]:
    """Yield frames from the demo video at the configured cadence."""
    capture = cv2.VideoCapture(VIDEO_PATH)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 1.0)
    stride = max(int(round(fps * FRAME_INTERVAL_SECONDS)), 1)
    index = 0
    frame_index = 1
    try:
        while capture.isOpened():
            ok, frame = capture.read()
            if not ok:
                break
            if index % stride == 0:
                encoded = _encode_frame(frame)
                if encoded:
                    yield {
                        "frame_index": frame_index,
                        "source_offset_seconds": index / fps,
                        "frame_b64": encoded,
                    }
                    frame_index += 1
            index += 1
    finally:
        capture.release()
