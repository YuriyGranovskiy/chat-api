#!/usr/bin/env bash
# Start whisper_service with a local venv (created in this directory).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV="${WHISPER_VENV:-$ROOT/.venv}"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
UVICORN="$VENV/bin/uvicorn"

if [[ ! -x "$PY" ]]; then
  echo "Creating venv at $VENV ..."
  python3 -m venv "$VENV"
fi

echo "Installing / updating dependencies ..."
"$PIP" install -q -r "$ROOT/requirements.txt"

if [[ "${WHISPER_CUDA_PIP:-0}" == "1" ]]; then
  echo "Installing CUDA 12 pip wheels (cuBLAS/cuDNN for libcublas.so.12) ..."
  "$PIP" install -q -r "$ROOT/requirements-cuda12.txt"
fi

HOST="${WHISPER_HOST:-127.0.0.1}"
PORT="${WHISPER_PORT:-8090}"

echo "Starting uvicorn on http://${HOST}:${PORT} (single worker) ..."
exec "$UVICORN" main:app --host "$HOST" --port "$PORT"
