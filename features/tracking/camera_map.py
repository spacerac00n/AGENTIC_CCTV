from __future__ import annotations

import streamlit as st

from config import HARDCODED_CAMERAS, LIVE_CAMERAS


def _status(camera_id: str, tracking: dict[str, object]) -> tuple[str, str, bool]:
    """Return the color, status text, and pulse state for one camera."""
    bolo = bool(tracking.get("bolo_active"))
    lost = bool(tracking.get("subject_lost"))
    active = bool(tracking.get("active")) and tracking.get("camera_id") == camera_id
    reacquired = bool(tracking.get("reacquired")) and tracking.get("reacquired_camera_id") == camera_id
    if camera_id == LIVE_CAMERAS[1]["camera_id"] and reacquired:
        return "#e74c3c", "RE-ACQUIRED", True
    if camera_id == LIVE_CAMERAS[0]["camera_id"] and lost:
        return "#e74c3c", "SUBJECT LOST — BOLO ACTIVE", True
    if active:
        return "#e74c3c", "TRACKING ACTIVE", False
    return "#2ecc71", "Monitoring", bolo


def _hardcoded() -> str:
    """Return the static hardcoded camera row HTML."""
    dots = []
    pulse = " pulse" if st.session_state["tracking"]["bolo_active"] else ""
    for camera in HARDCODED_CAMERAS:
        dots.append(f"<div class='node'><div class='dot yellow{pulse}'></div><div>{camera['name']}</div><small>{'BOLO ACTIVE' if pulse else 'Monitoring'}</small></div>")
    return "".join(dots)


def _live_camera(camera: dict[str, str]) -> None:
    """Render one clickable live camera icon."""
    color, status, pulse = _status(camera["camera_id"], st.session_state["tracking"])
    key = f"cam_button_{camera['camera_id'].lower().replace('-', '_')}"
    pulse_css = "animation:pulse 1.2s infinite;" if pulse else ""
    st.markdown(f"<style>.st-key-{key} button{{width:40px;height:40px;border-radius:999px;border:none;background:{color};color:transparent;{pulse_css}}}</style>", unsafe_allow_html=True)
    if st.button("●", key=key):
        st.session_state["active_camera"] = camera["camera_id"]
        st.rerun()
    st.markdown(f"**{camera['name']}**  \n<small>{status}</small>", unsafe_allow_html=True)


def render_camera_map() -> None:
    """Render the global five-camera map and navigation controls."""
    st.markdown("<style>@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(231,76,60,.7)}50%{box-shadow:0 0 0 16px rgba(231,76,60,0)}}.map{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.node{text-align:center}.dot{width:40px;height:40px;border-radius:999px;margin:0 auto 8px}.yellow{background:#f1c40f}.pulse{animation:pulse 1.2s infinite}</style>", unsafe_allow_html=True)
    st.markdown(f"<div class='map'>{_hardcoded()}</div>", unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        _live_camera(LIVE_CAMERAS[0])
    with right:
        _live_camera(LIVE_CAMERAS[1])
