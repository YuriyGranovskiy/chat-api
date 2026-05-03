from __future__ import annotations

import json
from typing import Any

import httpx
from flask import current_app
from werkzeug.datastructures import FileStorage


class WhisperTranscriptionError(Exception):
    """Raised when transcription cannot be completed; carries HTTP status for the API route."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _audio_magic_mime(data: bytes) -> str | None:
    if len(data) >= 4 and data[:4] == b"\x1a\x45\xdf\xa3":
        return "audio/webm"
    if len(data) >= 4 and data[:4] == b"RIFF":
        return "audio/wav"
    if len(data) >= 3 and data[:3] == b"ID3":
        return "audio/mpeg"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "audio/mpeg"
    if len(data) >= 4 and data[:4] == b"OggS":
        return "audio/ogg"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "audio/mp4"
    if len(data) >= 4 and data[:4] == b"fLaC":
        return "audio/flac"
    return None


def _resolve_audio_mime(file_storage: FileStorage, data: bytes) -> str | None:
    raw = (file_storage.mimetype or "").split(";")[0].strip().lower()
    allowed: frozenset[str] = current_app.config["ALLOWED_AUDIO_MIMES"]
    if raw in allowed:
        return raw
    magic = _audio_magic_mime(data)
    if magic in allowed:
        return magic
    return None


def _filename_for_mime(mime: str) -> str:
    return {
        "audio/webm": "audio.webm",
        "video/webm": "audio.webm",
        "audio/wav": "audio.wav",
        "audio/x-wav": "audio.wav",
        "audio/wave": "audio.wav",
        "audio/mpeg": "audio.mp3",
        "audio/mp3": "audio.mp3",
        "audio/ogg": "audio.ogg",
        "audio/mp4": "audio.m4a",
        "audio/x-m4a": "audio.m4a",
        "audio/flac": "audio.flac",
    }.get(mime, "audio.bin")


def validate_audio_file(file_storage: FileStorage) -> tuple[bytes, str, str]:
    """Read upload, enforce size and MIME. Returns (raw bytes, detected mime, filename for upstream)."""
    if not file_storage or not file_storage.filename:
        raise ValueError("No audio file")

    data = file_storage.read()
    if not data:
        raise ValueError("Empty audio file")

    max_bytes: int = current_app.config["MAX_AUDIO_BYTES"]
    if len(data) > max_bytes:
        raise ValueError("Audio file too large")

    mime = _resolve_audio_mime(file_storage, data)
    if not mime:
        raise ValueError("Unsupported audio type")

    return data, mime, _filename_for_mime(mime)


def transcribe_audio(
    audio_bytes: bytes,
    upload_filename: str,
    content_type: str,
    language: str | None,
) -> str:
    url = (current_app.config.get("WHISPER_TRANSCRIPTION_URL") or "").strip()
    if not url:
        raise WhisperTranscriptionError(
            "Speech transcription is not configured (WHISPER_TRANSCRIPTION_URL)",
            status_code=502,
        )

    timeout = httpx.Timeout(current_app.config["WHISPER_HTTP_TIMEOUT_SEC"])
    headers: dict[str, str] = {}
    api_key = current_app.config.get("WHISPER_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    files = {"file": (upload_filename, audio_bytes, content_type)}
    data: dict[str, Any] = {}
    if language and language.strip():
        data["language"] = language.strip()

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, files=files, data=data, headers=headers)
    except httpx.RequestError as exc:
        raise WhisperTranscriptionError(
            f"Transcription service unreachable: {exc}",
            status_code=502,
        ) from exc

    if response.status_code >= 400:
        detail = response.text[:500] if response.text else response.reason_phrase
        raise WhisperTranscriptionError(
            f"Transcription service error ({response.status_code}): {detail}",
            status_code=502,
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise WhisperTranscriptionError(
            "Transcription service returned invalid JSON",
            status_code=502,
        ) from exc

    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str):
        raise WhisperTranscriptionError(
            "Transcription service response missing text",
            status_code=502,
        )
    return text
