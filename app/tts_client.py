"""HTTP client for XTTS sidecar synthesis (tts_service)."""

from __future__ import annotations

import httpx
from flask import current_app


class TTSSynthesisError(Exception):
    """Raised when TTS cannot complete; carries HTTP status for the API route."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_tts_language(language: str | None) -> str:
    raw = (language or "en").strip().lower()
    if not raw:
        return "en"
    if "-" in raw:
        raw = raw.split("-")[0]
    return raw[:8] if len(raw) <= 8 else raw[:8]


def synthesize_speech(text: str, language: str | None) -> tuple[bytes, str]:
    trimmed = text.strip()
    if not trimmed:
        raise TTSSynthesisError("Text is empty", status_code=400)

    url = (current_app.config.get("TTS_SYNTHESIS_URL") or "").strip()
    if not url:
        raise TTSSynthesisError(
            "Speech synthesis is not configured (TTS_SYNTHESIS_URL)",
            status_code=502,
        )

    payload = {"text": trimmed, "language": normalize_tts_language(language)}
    timeout = httpx.Timeout(current_app.config["TTS_HTTP_TIMEOUT_SEC"])
    headers: dict[str, str] = {"Accept": "audio/wav, audio/mpeg, audio/*, application/octet-stream"}
    api_key = current_app.config.get("TTS_SYNTHESIS_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = httpx.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.RequestError as exc:
        raise TTSSynthesisError(
            f"TTS service unreachable: {exc}",
            status_code=502,
        ) from exc

    if response.status_code != 200:
        detail = (
            response.text[:500].strip()
            if response.headers.get("content-type", "").startswith("text/")
            else response.reason_phrase
        )
        code = (
            response.status_code
            if 400 <= response.status_code < 600
            else 502
        )
        raise TTSSynthesisError(
            f"TTS service error ({response.status_code}): {detail}",
            status_code=min(code, 504),
        )

    body = response.content
    if not body:
        raise TTSSynthesisError(
            "TTS service returned empty body",
            status_code=502,
        )

    content_type_raw = (
        response.headers.get("Content-Type") or ""
    ).split(";")[0].strip().lower()
    mime = content_type_raw or "audio/wav"
    return body, mime
