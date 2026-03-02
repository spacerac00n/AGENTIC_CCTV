from __future__ import annotations

import base64
import html
import random
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import HARDCODED_CAMERAS, LIVE_CAMERAS


_MAP_IMAGE_PATH = Path(__file__).resolve().parents[2] / "Map" / "map.png"
_NODE_POSITIONS: dict[str, tuple[float, float]] = {
    "CAM-WW": (15.0, 19.0),
    "CAM-XX": (38.0, 18.0),
    "CAM-YY": (63.0, 17.0),
    "CAM-ZZ": (82.0, 16.0),
    "CAM-LIVE-01": (31.0, 62.0),
    "CAM-LIVE-02": (70.0, 55.0),
}
_MAP_GLOW_CAMERA_IDS = (
    "CAM-WW",
    "CAM-XX",
    "CAM-YY",
    "CAM-ZZ",
    "CAM-LIVE-01",
)
_MAP_GLOW_COLORS = {
    "green": "#2ecc71",
    "yellow": "#f1c40f",
    "orange": "#e67e22",
    "red": "#e74c3c",
}
_MAP_GLOW_PATTERNS = (
    ["green", "green", "green", "yellow", "orange"],
    ["green", "green", "yellow", "orange", "red"],
)


def _format_map_time(total_minutes: int) -> str:
    """Return a HH:MM display string for the map time slider."""
    hours = (int(total_minutes) // 60) % 12
    minutes = int(total_minutes) % 60
    return f"{hours:02d}:{minutes:02d}"


def _format_event_time(value: object) -> str:
    """Return a readable local event time for tooltip display."""
    text = str(value).strip()
    if not text:
        return "--"
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return stamp.astimezone().strftime("%H:%M:%S")


def _format_confidence(value: object) -> str:
    """Return a consistent confidence label for map tooltips."""
    text = str(value).strip().lower()
    mapping = {
        "low": "25%",
        "medium": "50%",
        "high": "75%",
        "very high": "90%",
        "very_high": "90%",
        "certain": "90%",
    }
    if not text:
        return "--"
    if text in mapping:
        return mapping[text]
    if text.endswith("%"):
        return text
    return text.title()


def _tooltip_frame_src(
    camera_id: str,
    status: str,
    tracking: dict[str, object],
) -> str:
    """Return a data URI for the tooltip frame preview when available."""
    last_sighting = dict(tracking.get("last_sighting", {}))
    if status == "TARGET SPOTTED" and last_sighting.get("camera_id") == camera_id:
        frame_b64 = str(last_sighting.get("frame_b64", "")).strip()
        if frame_b64:
            return f"data:image/jpeg;base64,{frame_b64}"
    if tracking.get("search_camera_id") == camera_id:
        camera_state = dict(st.session_state.get("cameras", {}).get(camera_id, {}))
        frame_b64 = str(camera_state.get("current_frame", "")).strip()
        if frame_b64:
            return f"data:image/jpeg;base64,{frame_b64}"
    if tracking.get("source_camera_id") == camera_id:
        frame_b64 = str(st.session_state.get("incident_state", {}).get("frame_b64", "")).strip()
        if frame_b64:
            return f"data:image/jpeg;base64,{frame_b64}"
    return ""


def _map_image_data_uri() -> str | None:
    """Return the bundled reference map as a data URI."""
    if not _MAP_IMAGE_PATH.exists():
        return None
    suffix = _MAP_IMAGE_PATH.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(_MAP_IMAGE_PATH.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def _map_demo_glows(total_minutes: int) -> dict[str, str]:
    """Return a deterministic weighted glow assignment for the map demo."""
    seed = max(int(total_minutes), 0)
    cameras = list(_MAP_GLOW_CAMERA_IDS)
    glows = list(_MAP_GLOW_PATTERNS[(seed // 5) % len(_MAP_GLOW_PATTERNS)])
    rng = random.Random(seed)
    rng.shuffle(glows)
    return dict(zip(cameras, glows))


def _base_status(camera_id: str, tracking: dict[str, object]) -> tuple[str, str, bool]:
    """Return the default color, status text, and pulse state for one camera."""
    active = bool(tracking.get("active"))
    last_sighting = dict(tracking.get("last_sighting", {}))
    if camera_id and last_sighting.get("camera_id") == camera_id:
        return "#e74c3c", "TARGET SPOTTED", True
    if active and tracking.get("source_camera_id") == camera_id:
        return "#e67e22", "TRACK SOURCE", True
    if active and tracking.get("search_camera_id") == camera_id:
        return "#3498db", "TRACKING SEARCH", True
    if active:
        return "#f1c40f", "TRACKING MODE", True
    return "#2ecc71", "Monitoring", False


def _tracking_focus_status(camera_id: str, tracking: dict[str, object]) -> tuple[str, str, bool] | None:
    """Return only the explicitly tracked camera states for Tracker mode."""
    if not bool(tracking.get("active")):
        return None
    last_sighting = dict(tracking.get("last_sighting", {}))
    if camera_id and last_sighting.get("camera_id") == camera_id:
        return "#e74c3c", "TARGET SPOTTED", True
    if tracking.get("source_camera_id") == camera_id:
        return "#e67e22", "TRACK SOURCE", True
    if tracking.get("search_camera_id") == camera_id:
        return "#3498db", "TRACKING SEARCH", True
    return None


def _node_status(
    camera_id: str,
    tracking: dict[str, object],
    demo_glows: dict[str, str],
    enable_glow: bool,
) -> tuple[str, str, bool]:
    """Return the map node status, using slider-driven demo glows when idle."""
    if not enable_glow:
        focus_status = _tracking_focus_status(camera_id, tracking)
        if focus_status is not None:
            return focus_status
        return "#2ecc71", "Monitoring", False
    color, status, pulse = _base_status(camera_id, tracking)
    if pulse:
        return color, status, pulse
    demo_glow = demo_glows.get(camera_id)
    if not demo_glow:
        return color, status, pulse
    return _MAP_GLOW_COLORS[demo_glow], "Monitoring", True


def _node_tooltip_markup(
    camera_id: str,
    x_position: float,
    status: str,
    tracking: dict[str, object],
) -> str:
    """Return the hover tooltip markup for active map nodes."""
    if camera_id == LIVE_CAMERAS[0]["camera_id"]:
        return ""
    if status == "Monitoring":
        return ""
    last_sighting = dict(tracking.get("last_sighting", {}))
    incident_state = dict(st.session_state.get("incident_state", {}))
    frame_value = "--"
    confidence_value = "--"
    time_value = "--"
    threat_value = str(tracking.get("threat_type", "Unknown")).strip() or "Unknown"
    frame_src = _tooltip_frame_src(camera_id, status, tracking)
    if status == "TARGET SPOTTED" and last_sighting.get("camera_id") == camera_id:
        frame_value = str(last_sighting.get("frame_index", "--"))
        confidence_value = _format_confidence(last_sighting.get("confidence", ""))
        time_value = _format_event_time(
            last_sighting.get("last_seen_timestamp", last_sighting.get("timestamp", ""))
        )
    elif tracking.get("source_camera_id") == camera_id:
        frame_value = str(incident_state.get("frame_index", "--"))
        confidence_value = _format_confidence(incident_state.get("confidence", ""))
        time_value = _format_event_time(incident_state.get("timestamp", tracking.get("started_at", "")))
        threat_value = str(incident_state.get("threat_type", threat_value)).strip() or threat_value
    elif tracking.get("search_camera_id") == camera_id:
        frame_value = str(last_sighting.get("frame_index", incident_state.get("frame_index", "--")))
        confidence_value = _format_confidence(last_sighting.get("confidence", "tracking"))
        time_value = _format_event_time(
            last_sighting.get("last_seen_timestamp", tracking.get("started_at", ""))
        )
    side_class = " map-node-tooltip-left" if x_position >= 65 else ""
    image_markup = (
        "<img class='map-node-tooltip-image' "
        f"src='{html.escape(frame_src)}' alt='Frame preview' />"
        if frame_src
        else ""
    )
    return (
        f"<div class='map-node-tooltip{side_class}'>"
        f"{image_markup}"
        f"<div class='map-node-tooltip-line'><strong>Frame:</strong> {html.escape(frame_value)}</div>"
        f"<div class='map-node-tooltip-line'><strong>Confidence:</strong> {html.escape(confidence_value)}</div>"
        f"<div class='map-node-tooltip-line'><strong>Time:</strong> {html.escape(time_value)}</div>"
        f"<div class='map-node-tooltip-line'><strong>Threat type:</strong> {html.escape(threat_value.replace('_', ' ').title())}</div>"
        "</div>"
    )


def _node_markup(
    camera_id: str,
    label: str,
    tracking: dict[str, object],
    demo_glows: dict[str, str],
    enable_glow: bool,
) -> str:
    """Return one positioned node marker on the image map."""
    x, y = _NODE_POSITIONS.get(camera_id, (50.0, 50.0))
    color, status, pulse = _node_status(camera_id, tracking, demo_glows, enable_glow)
    pulse_class = " map-node-pulse" if pulse else ""
    warning_class = " map-node-warning" if status == "TARGET SPOTTED" else ""
    shadow = f"box-shadow:0 0 14px {color};" if enable_glow else ""
    tooltip_markup = _node_tooltip_markup(camera_id, x, status, tracking)
    status_markup = (
        f"<span class='map-node-status'>{status}</span>"
        if status != "Monitoring"
        else ""
    )
    return (
        f"<div class='map-node{pulse_class}{warning_class}' style='left:{x}%;top:{y}%;'>"
        f"<span class='map-node-dot' style='background:{color};{shadow}'></span>"
        f"<span class='map-node-label'>{label}</span>"
        f"{status_markup}"
        f"{tooltip_markup}"
        "</div>"
    )


def _map_markup(view_mode: str, total_minutes: int, enable_glow: bool) -> str:
    """Return the overlay HTML for the reference map."""
    tracking = dict(st.session_state.get("tracking", {}))
    demo_glows = _map_demo_glows(total_minutes)
    nodes = []
    for camera in HARDCODED_CAMERAS:
        nodes.append(
            _node_markup(
                str(camera["camera_id"]),
                str(camera["name"]),
                tracking,
                demo_glows,
                enable_glow,
            )
        )
    for camera in LIVE_CAMERAS:
        nodes.append(
            _node_markup(
                str(camera["camera_id"]),
                str(camera["name"]),
                tracking,
                demo_glows,
                enable_glow,
            )
        )
    image_uri = _map_image_data_uri()
    if not image_uri:
        return ""
    image_filter = (
        "grayscale(1) contrast(1.28) brightness(1.04)"
        if str(view_mode).strip().lower() == "bw"
        else "none"
    )
    return (
        "<style>"
        "@keyframes mapPulse{0%,100%{transform:translate(-50%,-50%) scale(1);opacity:1}"
        "50%{transform:translate(-50%,-50%) scale(1.18);opacity:.55}}"
        "@keyframes mapWarningGlow{0%,100%{transform:translate(-50%,-50%) scale(1);opacity:1}"
        "50%{transform:translate(-50%,-50%) scale(1.32);opacity:.62}}"
        ".map-stage{position:relative;width:100%;aspect-ratio:500/314;border-radius:18px;"
        "overflow:hidden;border:1px solid rgba(255,255,255,.08);"
        "box-shadow:0 14px 28px rgba(0,0,0,.18);background:#050914;}"
        ".map-base{position:absolute;inset:0;background-size:cover;background-position:center;}"
        ".map-node{position:absolute;transform:translate(-50%,-50%);display:flex;flex-direction:column;"
        "align-items:center;gap:4px;text-align:center;min-width:76px;z-index:2;}"
        ".map-node-tooltip{display:none;position:absolute;left:calc(100% + 12px);top:50%;"
        "transform:translateY(-50%);min-width:188px;padding:.55rem .65rem;border-radius:12px;"
        "background:rgba(5,9,20,.96);border:1px solid rgba(255,255,255,.12);"
        "box-shadow:0 10px 24px rgba(0,0,0,.28);text-align:left;z-index:5;pointer-events:none;}"
        ".map-node-tooltip-left{left:auto;right:calc(100% + 12px);}"
        ".map-node:hover .map-node-tooltip{display:block;}"
        ".map-node-tooltip-image{display:block;width:100%;height:86px;object-fit:cover;"
        "border-radius:8px;border:1px solid rgba(255,255,255,.08);margin-bottom:.5rem;}"
        ".map-node-tooltip-line{color:#ffffff;font-size:.74rem;font-weight:500;line-height:1.4;"
        "white-space:nowrap;}"
        ".map-node-warning::before{content:'';position:absolute;left:50%;top:0;"
        "width:148px;height:148px;border-radius:999px;pointer-events:none;"
        "background:radial-gradient(circle, rgba(231,76,60,.78) 0%, rgba(231,76,60,.46) 28%, rgba(231,76,60,.18) 52%, rgba(231,76,60,0) 76%);"
        "transform:translate(-50%,-50%);animation:mapWarningGlow 1.05s infinite ease-in-out;z-index:-1;}"
        ".map-node-dot{width:18px;height:18px;border-radius:999px;border:2px solid rgba(255,255,255,.88);}"
        ".map-node-pulse .map-node-dot{animation:mapPulse 1.25s infinite;}"
        ".map-node-warning .map-node-dot{width:28px;height:28px;border-width:3px;"
        "box-shadow:0 0 28px rgba(231,76,60,1),0 0 56px rgba(231,76,60,.82),0 0 84px rgba(231,76,60,.48) !important;}"
        ".map-node-label{padding:.2rem .45rem;border-radius:999px;background:rgba(4,10,20,.82);"
        "color:#fff;font-size:.72rem;font-weight:700;line-height:1.1;}"
        ".map-node-status{padding:.16rem .38rem;border-radius:999px;background:rgba(4,10,20,.72);"
        "color:rgba(255,255,255,.78);font-size:.62rem;font-weight:600;line-height:1.1;}"
        "</style>"
        "<div class='map-stage'>"
        f"<div class='map-base' style=\"background-image:linear-gradient(rgba(6,10,18,.1),rgba(6,10,18,.18)),url('{image_uri}');filter:{image_filter};\"></div>"
        f"{''.join(nodes)}"
        "</div>"
    )


def _hardcoded() -> str:
    """Return the static hardcoded camera row HTML."""
    dots = []
    active = bool(st.session_state["tracking"]["active"])
    pulse = " pulse" if active else ""
    status = "TRACKING MODE" if active else "Monitoring"
    for camera in HARDCODED_CAMERAS:
        dots.append(
            "<div class='node'><div class='dot yellow"
            f"{pulse}'></div><div>{camera['name']}</div><small>{status}</small></div>"
        )
    return "".join(dots)


def _live_camera(camera: dict[str, str], enable_glow: bool = True) -> None:
    """Render one clickable live camera icon."""
    tracking = dict(st.session_state.get("tracking", {}))
    if not enable_glow:
        focus_status = _tracking_focus_status(camera["camera_id"], tracking)
        if focus_status is not None:
            color, status, pulse = focus_status
        else:
            color, status, pulse = "#2ecc71", "Monitoring", False
    else:
        color, status, pulse = _base_status(camera["camera_id"], tracking)
    key = f"cam_button_{camera['camera_id'].lower().replace('-', '_')}"
    pulse_css = "animation:pulse 1.6s infinite;" if pulse and not enable_glow else ""
    if pulse and enable_glow:
        pulse_css = "animation:pulse 1.2s infinite;"
    st.markdown(f"<style>.st-key-{key} button{{width:40px;height:40px;border-radius:999px;border:none;background:{color};color:transparent;{pulse_css}}}</style>", unsafe_allow_html=True)
    if st.button("●", key=key):
        st.session_state["active_camera"] = camera["camera_id"]
        st.rerun()
    st.markdown(f"**{camera['name']}**  \n<small>{status}</small>", unsafe_allow_html=True)


def render_tracker_cameras(enable_glow: bool = True) -> None:
    """Render the live camera shortcuts used by the Tracker tab."""
    left, right = st.columns(2)
    with left:
        _live_camera(LIVE_CAMERAS[0], enable_glow=enable_glow)
    with right:
        _live_camera(LIVE_CAMERAS[1], enable_glow=enable_glow)


def render_camera_map(
    key_prefix: str = "map_tab",
    heading: str = "Map",
    enable_glow: bool = True,
) -> None:
    """Render the reference map page and camera navigation controls."""
    st.markdown(f"**{heading}**")
    st.markdown(
        "<style>"
        "div[data-testid='stSlider'] div[data-testid='stSliderThumbValue']{display:none !important;}"
        "</style>",
        unsafe_allow_html=True,
    )
    controls_left, controls_right = st.columns((0.3, 0.7), gap="small")
    with controls_left:
        view_mode = st.selectbox(
            "Map View",
            options=["Satallite", "BW"],
            key=f"{key_prefix}_map_view_mode",
        )
    with controls_right:
        slider_col, time_col = st.columns((0.82, 0.18), gap="small")
        with slider_col:
            time_minutes = st.slider(
                "Map Time",
                min_value=0000,
                max_value=2359,
                value=360,
                step=1,
                key=f"{key_prefix}_map_time_slider",
            )
        with time_col:
            st.markdown(
                "<div style='margin-top:1.9rem;padding:0.52rem 0.6rem;border-radius:10px;"
                "border:1px solid rgba(255,255,255,0.12);background:#0f172a;color:#ffffff;"
                "font-size:0.95rem;font-weight:700;line-height:1.1;text-align:center;'>"
                f"{_format_map_time(time_minutes)}</div>",
                unsafe_allow_html=True,
            )
    if _MAP_IMAGE_PATH.exists():
        st.markdown(_map_markup(view_mode, time_minutes, enable_glow), unsafe_allow_html=True)
    else:
        st.error(f"Map image not found: {_MAP_IMAGE_PATH}")
