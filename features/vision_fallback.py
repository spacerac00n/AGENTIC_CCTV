from __future__ import annotations

import json
import urllib.error
import urllib.request

from config import OLLAMA_HOST, OLLAMA_VISION_MODEL

_OLLAMA_GENERATE_URL = f"{OLLAMA_HOST.rstrip('/')}/api/generate"
_OLLAMA_TIMEOUT_SECONDS = 20


def extract_json_payload(raw_text: str) -> dict[str, object]:
    """Parse a JSON object from plain text or a fenced JSON block."""
    text = raw_text.strip()
    if not text:
        return {}
    candidates = (
        text,
        text.removeprefix("```json").removeprefix("```").removesuffix("```").strip(),
    )
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _request_openai_json(
    client: object,
    model: str,
    system_prompt: str,
    user_prompt: str,
    frame_b64: str,
) -> dict[str, object]:
    """Request JSON from the primary OpenAI vision model."""
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{frame_b64}",
                    },
                ],
            },
        ],
    )
    return extract_json_payload(str(getattr(response, "output_text", "")))


def _request_ollama_json(
    system_prompt: str,
    user_prompt: str,
    frame_b64: str,
) -> dict[str, object]:
    """Request JSON from the local Ollama vision fallback model."""
    body = json.dumps(
        {
            "model": OLLAMA_VISION_MODEL,
            "system": system_prompt,
            "prompt": user_prompt,
            "images": [frame_b64],
            "stream": False,
            "format": "json",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        _OLLAMA_GENERATE_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_OLLAMA_TIMEOUT_SECONDS) as response:
            raw_response = response.read().decode("utf-8")
    except (OSError, TimeoutError, urllib.error.URLError):
        return {}
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError:
        return {}
    return extract_json_payload(str(payload.get("response", "")))


def request_vision_json(
    *,
    client: object | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    frame_b64: str,
) -> tuple[dict[str, object], str, str]:
    """Return model JSON plus source and failure reason."""
    if not frame_b64:
        return {}, "fallback", "missing_frame"
    if client is None:
        ollama_payload = _request_ollama_json(system_prompt, user_prompt, frame_b64)
        if ollama_payload:
            return ollama_payload, "ollama", "primary_unavailable"
        return {}, "fallback", "primary_unavailable"
    try:
        openai_payload = _request_openai_json(client, model, system_prompt, user_prompt, frame_b64)
    except Exception:
        ollama_payload = _request_ollama_json(system_prompt, user_prompt, frame_b64)
        if ollama_payload:
            return ollama_payload, "ollama", "primary_request_failed"
        return {}, "fallback", "primary_request_failed"
    if openai_payload:
        return openai_payload, "openai", ""
    return {}, "fallback", "primary_invalid_response"
