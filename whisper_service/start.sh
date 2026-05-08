#!/usr/bin/env bash
# Start whisper_service with a local venv (created in this directory).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
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

VENV_PATH="$(pwd)/.venv/lib/python3.12/site-packages"

# Собираем все пути к библиотекам NVIDIA
CUBLAS_LIB="$VENV_PATH/nvidia/cublas/lib"
CUDNN_LIB="$VENV_PATH/nvidia/cudnn/lib"
CUDA_RT_LIB="$VENV_PATH/nvidia/cuda_runtime/lib"

# Экспортируем их для всех дочерних процессов (включая uvicorn)
export LD_LIBRARY_PATH="$CUBLAS_LIB:$CUDNN_LIB:$CUDA_RT_LIB:${LD_LIBRARY_PATH}"

echo "Starting uvicorn on http://${HOST}:${PORT} (single worker) ..."
exec "$UVICORN" main:app --host "$HOST" --port "$PORT"
