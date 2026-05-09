# chat-api

## Speech transcription (`whisper_service`)

Transcription runs in a **separate process** in [`whisper_service/`](whisper_service/) (faster-whisper + FastAPI). The main Flask app proxies uploads to it when `WHISPER_TRANSCRIPTION_URL` is set.

### Local development

1. Start the sidecar (creates `whisper_service/.venv`, installs deps, runs a **single** uvicorn worker on **127.0.0.1:8090**):

   ```bash
   cd whisper_service
   ./start.sh
   ```

   Optional: `WHISPER_HOST`, `WHISPER_PORT` (default `8090`), `WHISPER_VENV` (default `./.venv` in that folder). **GPU + missing cuBLAS:** if you see `Library libcublas.so.12 is not found`, install CUDA 12 user-space libs into the same venv, then restart:

   ```bash
   cd whisper_service
   WHISPER_CUDA_PIP=1 ./start.sh
   ```

   (Same as: `.venv/bin/pip install -r whisper_service/requirements-cuda12.txt`.) If it still fails, install the [NVIDIA CUDA Toolkit](https://developer.nvidia.com/cuda-downloads) matching your driver, or force CPU: `WHISPER_DEVICE=cpu ./start.sh`.

   For a fully manual venv, use `pip install -r whisper_service/requirements.txt` and `uvicorn main:app --host 127.0.0.1 --port 8090`.

2. Point the API at the sidecar:

   ```bash
   export WHISPER_TRANSCRIPTION_URL=http://127.0.0.1:8090/v1/audio/transcriptions
   ```

3. Run the Flask app as you usually do.

Optional sidecar environment variables:

| Variable | Meaning |
|----------|---------|
| `WHISPER_MODEL` | faster-whisper model id (default `small`) |
| `WHISPER_DEVICE` | Empty = **auto**: `cuda` if [CTranslate2](https://opennmt.net/CTranslate2/installation.html) sees a GPU, else `cpu`. Set `cuda` or `cpu` to force. |
| `WHISPER_COMPUTE_TYPE` | Empty = **auto**: `float16` on GPU, `int8` on CPU. Override e.g. `int8_float16` on GPU if you tune VRAM. |
| `MAX_AUDIO_BYTES` | Max upload size for the sidecar (default 25 MiB) |

**GPU still slow or log shows `device='cpu'`?** The PyPI `ctranslate2` wheel must match your CUDA drivers (see CTranslate2 “Install with GPU support”). Install the suggested NVIDIA packages, then reinstall `faster-whisper` / `ctranslate2` in `whisper_service/.venv`, or set explicitly:

`WHISPER_DEVICE=cuda WHISPER_COMPUTE_TYPE=float16 ./start.sh`

Model weights are downloaded on first use (Hugging Face cache, typically under `~/.cache/huggingface`). To keep caches outside the repo, leave defaults; if you set `HF_HOME` or similar **inside** the repo tree, add that path to `.gitignore` (`.cache/` is already ignored for common layouts).

### HTTP API (from the UI)

- `POST /api/chats/{chat_id}/transcriptions` — `multipart/form-data` with field **`audio`** (file) and optional **`language`** (overrides the chat default). If omitted, the chat's **`language`** is sent to the transcription service. Response: `{"text":"..."}` (leading/trailing whitespace trimmed). Non-empty results are saved as a **user** message and broadcast on the **`new_message`** WebSocket exactly like **`send_message`**, so the client does not need `POST /messages`; the assistant reply is still produced by the background worker and emitted as usual.

If `WHISPER_TRANSCRIPTION_URL` is unset, the transcribe endpoint returns **502** with a clear error; the rest of the API keeps running.


## Chat speech language

Each chat has a **`language`** field (ISO 639-1 style, e.g. `en`, `ru`). It is used as the default hint for **`POST /api/chats/{id}/transcriptions`** when the multipart form does not include `language`.

- **`POST /api/chats`** — optional JSON field **`language`** (default **`en`**). Invalid values fall back to `en`.
- **`GET /api/chats`** — each item includes **`language`**.
- **`GET /api/chats/{id}`** — response includes **`language`**.

Run `python3 scripts/migrate_local_db.py` on existing SQLite DBs to add **`chat.language`**, **`message.assistant_speech_path`**, and related columns (existing chat rows keep default `language`).

## Speech synthesis (`tts_service`)

Assistant messages can be synthesized with **Coqui XTTS v2** using a sidecar in [`tts_service/`](tts_service/), similar to Whisper.

1. Provide a short **reference speaker** `.wav` and set **`XTTS_SPEAKER_WAV`** to its path (required for `/v1/speech`).

2. Start the sidecar (heavy: torch + Coqui **TTS**; first request may download model weights):

   ```bash
   cd tts_service
   export XTTS_SPEAKER_WAV=/path/to/ref.wav
   ./start.sh
   ```

   Defaults bind **127.0.0.1:8091**. Optional: **`TTS_HOST`**, **`TTS_PORT`**, **`XTTS_USE_GPU=0`** for CPU-only, **`XTTS_MODEL`** for a different XTTS checkpoint id.

3. Point the Flask app at the synthesizer URL (either variable works):

   ```bash
   export TTS_SYNTHESIS_URL=http://127.0.0.1:8091/v1/speech
   # optional alias:
   export XTTS_SYNTHESIS_URL=http://127.0.0.1:8091/v1/speech
   ```

4. API (same JWT as other chat routes):

   - **`POST /api/chats/{chat_id}/messages/{message_id}/speech`** — run XTTS (or return cache) as **audio/wav**; **`X-Cached-Speech: 1`** when a stored file was reused. Optional **`language`** query overrides the chat default.
   - **`GET`** the same URL — fetch stored speech, **404** if absent.

Unset **`TTS_SYNTHESIS_URL`** → **`POST`** returns **502**.

Message payloads from **`GET …/messages`**, **`GET /chats/{id}`**, and WebSocket **`new_message`** include **`has_speech`** (`true` when synthesis was stored for an assistant row).
