"""OpenAI-style audio transcription HTTP service backed by faster-whisper.

Run with a single worker (default): uvicorn main:app --host 127.0.0.1 --port 8090
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

logger = logging.getLogger(__name__)

app = FastAPI(title="whisper_service", version="1.0.0")

_model = None


def _detect_device() -> str:
    """Use WHISPER_DEVICE if set; otherwise cuda when CTranslate2 sees a GPU."""
    raw = (os.environ.get("WHISPER_DEVICE") or "").strip()
    if raw:
        return raw
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception as exc:
        logger.warning("CUDA probe skipped (%s); using CPU", exc)
    return "cpu"


def _default_compute_type(device: str) -> str:
    """GPU: float16 is a good default on 8–16 GB VRAM. CPU: int8."""
    if device.lower().startswith("cuda"):
        return "float16"
    return "int8"


def _resolve_compute_type(device: str) -> str:
    raw = (os.environ.get("WHISPER_COMPUTE_TYPE") or "").strip()
    if raw:
        return raw
    return _default_compute_type(device)


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        model_name = os.environ.get("WHISPER_MODEL", "small")
        device = _detect_device()
        compute_type = _resolve_compute_type(device)
        logger.warning(
            "Loading WhisperModel model=%r device=%r compute_type=%r",
            model_name,
            device,
            compute_type,
        )
        _model = WhisperModel(model_name, device=device, compute_type=compute_type)
    return _model


def _suffix_for_upload(filename: str | None, content_type: str | None) -> str:
    name = (filename or "").lower()
    for ext in (".webm", ".wav", ".mp3", ".ogg", ".m4a", ".mp4", ".flac"):
        if name.endswith(ext):
            return ext
    ct = (content_type or "").split(";")[0].strip().lower()
    return {
        "audio/webm": ".webm",
        "video/webm": ".webm",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/wave": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/ogg": ".ogg",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/flac": ".flac",
    }.get(ct, ".webm")


@app.post("/v1/audio/transcriptions")
def transcribe(
    file: Annotated[UploadFile, File(description="Audio file")],
    language: str | None = Form(default=None),
    model: str | None = Form(default=None),
    response_format: str | None = Form(default=None),
):
    del model, response_format  # OpenAI-compatible unused fields

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    max_bytes = int(os.environ.get("MAX_AUDIO_BYTES", str(25 * 1024 * 1024)))
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail="File too large")

    suffix = _suffix_for_upload(file.filename, file.content_type)
    path: str | None = None
    try:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(data)

        whisper_model = _get_model()
        lang = (language or "").strip() or None
        segments, _info = whisper_model.transcribe(path, language=lang)
        text = "".join(segment.text for segment in segments).strip()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if path and os.path.isfile(path):
            try:
                os.unlink(path)
            except OSError:
                pass

    return {"text": text}
