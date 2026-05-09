"""Coqui XTTS v2 synthesis sidecar — returns WAV audio bytes."""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field


class SynthBody(BaseModel):
    text: str = Field(..., max_length=10000)
    language: str = "en"


def _normalized_language(language: str) -> str:
    raw = (language or "en").strip().lower()
    if not raw:
        return "en"
    primary = raw.split("-")[0]
    return primary[:8]


def _require_speaker_wav() -> Path:
    raw = os.environ.get("XTTS_SPEAKER_WAV", "").strip()
    if not raw:
        raise HTTPException(
            status_code=503,
            detail="XTTS_SPEAKER_WAV must point to a readable reference .wav file",
        )
    path = Path(raw).expanduser()
    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"XTTS_SPEAKER_WAV path not found or not a file: {path}",
        )
    return path


@lru_cache(maxsize=1)
def load_tts():
    """Load XTTS once (VRAM-heavy)."""

    from TTS.api import TTS

    model_name = os.environ.get(
        "XTTS_MODEL",
        "tts_models/multilingual/multi-dataset/xtts_v2",
    ).strip()

    gpu_env = os.environ.get("XTTS_USE_GPU", "1").strip().lower()
    use_gpu = gpu_env not in {"0", "false", ""}
    if use_gpu:
        try:
            import torch

            use_gpu = bool(torch.cuda.is_available())
        except ImportError:
            use_gpu = False

    return TTS(model_name=model_name, gpu=use_gpu)


app = FastAPI(title="tts_service", version="1.0.0")


@app.get("/health")
def health():
    speaker_ok = False
    try:
        speaker_ok = _require_speaker_wav().is_file()
    except HTTPException:
        speaker_ok = False
    return {"status": "ok", "speaker_wav_configured": speaker_ok}


@app.post("/v1/speech")
def synthesize(body: SynthBody):
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")

    speaker_path = str(_require_speaker_wav())
    lang = _normalized_language(body.language)

    tmp_path = None
    try:
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp_path = tmp_file.name
        tmp_file.close()

        tts = load_tts()
        tts.tts_to_file(
            text=text,
            file_path=tmp_path,
            speaker_wav=speaker_path,
            language=lang,
        )

        wav_bytes = Path(tmp_path).read_bytes()
        if not wav_bytes:
            raise HTTPException(status_code=500, detail="synthesizer produced empty output")
        return Response(content=wav_bytes, media_type="audio/wav")

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"synthesis failed: {exc!s}",
        ) from exc

    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
