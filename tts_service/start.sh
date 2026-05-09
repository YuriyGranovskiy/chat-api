#!/usr/bin/env bash
# XTTS sidecar — single-worker uvicorn (VRAM).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV="${TTS_VENV:-$ROOT/.venv}"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
UVICORN="$VENV/bin/uvicorn"

if [[ ! -x "$PY" ]]; then
  echo "Creating venv at $VENV ..."
  python3 -m venv "$VENV"
fi

echo "Installing / updating dependencies ..."
"$PIP" install -q -r "$ROOT/requirements.txt"

if [[ -z "${XTTS_SPEAKER_WAV:-}" ]]; then
  echo "Warning: XTTS_SPEAKER_WAV not set — /v1/speech will return 503 until you set it."
fi

HOST="${TTS_HOST:-127.0.0.1}"
PORT="${TTS_PORT:-8091}"

echo "Starting uvicorn on http://${HOST}:${PORT} (workers=1) ..."
exec "$UVICORN" main:app --host "$HOST" --port "$PORT" --workers 1
