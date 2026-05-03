# chat-api

## Speech transcription (`whisper_service`)

Transcription runs in a **separate process** in [`whisper_service/`](whisper_service/) (faster-whisper + FastAPI). The main Flask app proxies uploads to it when `WHISPER_TRANSCRIPTION_URL` is set.

### Local development

1. Install sidecar dependencies (prefer a dedicated venv or `pip install -r whisper_service/requirements.txt`).
2. Start the sidecar on **127.0.0.1:8090** with a **single** uvicorn worker (multiple workers load the model multiple times):

   ```bash
   cd whisper_service
   uvicorn main:app --host 127.0.0.1 --port 8090
   ```

3. Point the API at the sidecar:

   ```bash
   export WHISPER_TRANSCRIPTION_URL=http://127.0.0.1:8090/v1/audio/transcriptions
   ```

4. Run the Flask app as you usually do.

Optional sidecar environment variables:

| Variable | Meaning |
|----------|---------|
| `WHISPER_MODEL` | faster-whisper model id (default `small`) |
| `WHISPER_DEVICE` | `cpu` or `cuda` (default `cpu`) |
| `WHISPER_COMPUTE_TYPE` | e.g. `int8`, `float16` (default `int8` on CPU) |
| `MAX_AUDIO_BYTES` | Max upload size for the sidecar (default 25 MiB) |

Model weights are downloaded on first use (Hugging Face cache, typically under `~/.cache/huggingface`). To keep caches outside the repo, leave defaults; if you set `HF_HOME` or similar **inside** the repo tree, add that path to `.gitignore` (`.cache/` is already ignored for common layouts).

### HTTP API (from the UI)

- `POST /api/chats/{chat_id}/transcriptions` — `multipart/form-data` with field **`audio`** (file) and optional **`language`**. Requires JWT and membership in the chat. Response: `{"text":"..."}`.

If `WHISPER_TRANSCRIPTION_URL` is unset, the transcribe endpoint returns **502** with a clear error; the rest of the API keeps running.

