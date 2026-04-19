from __future__ import annotations

import json
import re


_FENCE_OPEN = re.compile(r"```\s*json\s*", re.IGNORECASE)


def _canonical_json_string(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def split_assistant_content(raw: str) -> tuple[str, str | None]:
    """
    Split visible narrative text and trailing scene JSON.
    Returns (display_text, canonical JSON string or None if not found / invalid).
    """
    fenced = _try_split_fenced_json(raw)
    if fenced is not None:
        return fenced

    return _try_split_trailing_json(raw)


def _try_split_fenced_json(raw: str) -> tuple[str, str | None] | None:
    match = _FENCE_OPEN.search(raw)
    if not match:
        return None
    block_start = match.start()
    inner_start = match.end()
    close = raw.find("```", inner_start)
    if close == -1:
        return None
    inner = raw[inner_start:close].strip()
    try:
        obj = json.loads(inner)
    except json.JSONDecodeError:
        return None
    meta = _canonical_json_string(obj)
    before = raw[:block_start].rstrip()
    after = raw[close + 3 :].lstrip()
    if after:
        display = f"{before}\n\n{after}".strip()
    else:
        display = before
    return display, meta


def _try_split_trailing_json(raw: str) -> tuple[str, str | None]:
    text = raw.rstrip()
    brace = text.rfind("{")
    if brace == -1:
        return raw, None
    try:
        obj, end = json.JSONDecoder().raw_decode(text[brace:])
    except json.JSONDecodeError:
        return raw, None
    if brace + end != len(text):
        return raw, None
    meta = _canonical_json_string(obj)
    display = text[:brace].rstrip()
    return display, meta


def assistant_content_for_model(display: str, meta: str | None) -> str:
    """Rebuild full assistant message text for the LLM (matches prior model output shape)."""
    if not meta:
        return display
    return f"{display.rstrip()}\n\n{meta}"


def assistant_raw_for_model(stored_message: str, assistant_meta: str | None) -> str:
    """Stored row -> text sent to the model (legacy rows keep full raw `message`)."""
    if assistant_meta is not None:
        return assistant_content_for_model(stored_message, assistant_meta)
    return stored_message


def assistant_display_for_client(message: str, assistant_meta: str | None) -> str:
    """Text shown in API/WebSocket; strips JSON for legacy rows without assistant_meta."""
    if assistant_meta is not None:
        return message
    display, _ = split_assistant_content(message)
    return display
