from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone

import cv2
import streamlit as st
from openai import OpenAI

from config import OPENAI_API_KEY_2, REACQUISITION_PROMPT_TEMPLATE, TRACKING_FRAME_INTERVAL, TRACKING_LOST_THRESHOLD, TRACKING_PROMPT_TEMPLATE, TRACKING_VLM_MODEL
from features.tracking.bolo_generator import generate_bolo
from features.tracking.tracking_state import TrackingState
def _encode(frame: object) -> str:
    """Return one OpenCV frame as base64 JPEG."""
    ok, buffer = cv2.imencode(".jpg", frame)
    return base64.b64encode(buffer.tobytes()).decode("utf-8") if ok else ""
def _frames(video_path: str):
    """Yield one sampled tracking frame every tracking interval."""
    capture = cv2.VideoCapture(video_path)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 1.0)
    stride = max(int(round(fps * TRACKING_FRAME_INTERVAL)), 1)
    index = 0
    try:
        while capture.isOpened():
            ok, frame = capture.read()
            if not ok:
                break
            if index % stride == 0:
                yield _encode(frame)
            index += 1
    finally:
        capture.release()
def _observe(frame_b64: str, prompt: str) -> dict[str, object]:
    """Return one Agent 2 VLM observation or a safe fallback."""
    if not OPENAI_API_KEY_2 or not frame_b64:
        return {"subject_visible": False, "last_position": "", "confidence": "low", "notes": ""}
    try:
        response = OpenAI(api_key=OPENAI_API_KEY_2).responses.create(model=TRACKING_VLM_MODEL, input=[{"role": "system", "content": prompt}, {"role": "user", "content": [{"type": "input_text", "text": "Analyze this frame."}, {"type": "input_image", "image_url": f"data:image/jpeg;base64,{frame_b64}"}]}])
        payload = json.loads(getattr(response, "output_text", ""))
    except Exception:
        return {"subject_visible": False, "last_position": "", "confidence": "low", "notes": ""}
    return payload if isinstance(payload, dict) else {"subject_visible": False}
def start_tracking(initial_state: TrackingState) -> None:
    """Run Agent 2 tracking until the subject is lost or re-acquired."""
    st.session_state["tracking"] = dict(initial_state)
    video_path = str(st.session_state["cameras"][initial_state["camera_id"]].get("video_path") or "")
    stream = _frames(video_path) if video_path else iter(())
    while True:
        tracking = dict(st.session_state["tracking"])
        if not tracking["active"] or tracking["reacquired"] or tracking["subject_lost"]:
            return
        frame_b64 = next(stream, "")
        prompt = TRACKING_PROMPT_TEMPLATE.format(subject_description=tracking["subject_description"], user_extra_context=tracking["user_extra_context"])
        observation = _observe(frame_b64, prompt) if frame_b64 else {"subject_visible": False, "notes": "Video ended", "confidence": "low", "last_position": ""}
        tracking["observations"] = list(tracking["observations"]) + [observation]
        tracking["consecutive_lost_count"] = 0 if observation.get("subject_visible") else tracking["consecutive_lost_count"] + 1
        if tracking["consecutive_lost_count"] >= TRACKING_LOST_THRESHOLD:
            tracking.update({"active": False, "subject_lost": True, "subject_lost_timestamp": datetime.now(timezone.utc).isoformat(), "bolo_text": generate_bolo(tracking), "bolo_active": True})
        st.session_state["tracking"] = tracking
        if tracking["subject_lost"]:
            return
        time.sleep(TRACKING_FRAME_INTERVAL)
def check_reacquisition(frame_b64: str, camera_id: str, frame_path: str) -> None:
    """Check BOLO reacquisition on Camera 2 frames and store the match."""
    tracking = dict(st.session_state.get("tracking", {}))
    if not tracking or not tracking.get("bolo_active") or tracking.get("reacquired"):
        return
    prompt = REACQUISITION_PROMPT_TEMPLATE.format(bolo_text=tracking.get("bolo_text", ""))
    observation = _observe(frame_b64, prompt)
    if observation.get("subject_visible"):
        tracking.update({"active": False, "reacquired": True, "reacquired_camera_id": camera_id, "reacquired_frame_path": frame_path or None, "reacquired_timestamp": datetime.now(timezone.utc).isoformat(), "reacquired_confidence": str(observation.get("confidence", ""))})
        st.session_state["tracking"] = tracking
