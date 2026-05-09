import os
from datetime import timedelta


class Config:
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///chat.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "my_secret_fro_socketio"
    JWT_SECRET_KEY = "my_jwt_secret_key"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=3)

    # Relative to project root; absolute path is set in create_app.
    MEDIA_FOLDER = "instance/media"
    MAX_IMAGE_BYTES = 10 * 1024 * 1024
    ALLOWED_IMAGE_MIMES = frozenset(
        {"image/png", "image/jpeg", "image/webp", "image/gif"}
    )
    MIME_TO_EXT = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }

    # Speech transcription (proxy to whisper_service). Empty URL → 502 on transcribe only.
    WHISPER_TRANSCRIPTION_URL = "http://localhost:8090/v1/audio/transcriptions" # os.environ.get("WHISPER_TRANSCRIPTION_URL", "").strip()
    WHISPER_HTTP_TIMEOUT_SEC = float(os.environ.get("WHISPER_HTTP_TIMEOUT_SEC", "120"))
    WHISPER_API_KEY = os.environ.get("WHISPER_API_KEY", "").strip() or None

    MAX_AUDIO_BYTES = int(os.environ.get("MAX_AUDIO_BYTES", str(25 * 1024 * 1024)))
    ALLOWED_AUDIO_MIMES = frozenset(
        {
            "audio/webm",
            "video/webm",
            "audio/wav",
            "audio/x-wav",
            "audio/wave",
            "audio/mpeg",
            "audio/mp3",
            "audio/ogg",
            "audio/mp4",
            "audio/x-m4a",
            "audio/flac",
        }
    )

    # XTTS v2 (tts_service HTTP). Empty URL yields 502 on speech routes only.
    TTS_SYNTHESIS_URL = (
        os.environ.get("TTS_SYNTHESIS_URL", "").strip()
        or os.environ.get("XTTS_SYNTHESIS_URL", "").strip()
    )
    TTS_HTTP_TIMEOUT_SEC = float(os.environ.get("TTS_HTTP_TIMEOUT_SEC", "300"))
    TTS_SYNTHESIS_API_KEY = os.environ.get("TTS_SYNTHESIS_API_KEY", "").strip() or None
