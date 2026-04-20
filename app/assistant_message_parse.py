from __future__ import annotations

import json
import re


_FENCE_OPEN = re.compile(r"```\s*json\s*", re.IGNORECASE)


def _canonical_json_string(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _repair_broken_top_level_object(candidate: str) -> str:
    """
    Heuristic repair for common LLM JSON glitches:
    - premature closing `}` of the top-level object before more keys follow
    - missing trailing `}` for the top-level object
    """
    out: list[str] = []
    depth = 0
    in_string = False
    escape = False
    for idx, char in enumerate(candidate):
        if escape:
            out.append(char)
            escape = False
            continue
        if char == "\\":
            out.append(char)
            if in_string:
                escape = True
            continue
        if char == '"':
            out.append(char)
            in_string = not in_string
            continue
        if in_string:
            out.append(char)
            continue
        if char == "{":
            depth += 1
            out.append(char)
            continue
        if char == "}":
            if depth <= 0:
                continue
            if depth == 1 and candidate[idx + 1 :].strip():
                # Skip premature close of top-level object when there is trailing content.
                continue
            depth -= 1
            out.append(char)
            continue
        out.append(char)

    if depth > 0:
        out.extend("}" * depth)
    return "".join(out).strip()


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
        repaired_inner = _repair_broken_top_level_object(inner)
        try:
            obj = json.loads(repaired_inner)
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
    search_end = len(text)
    while search_end > 0:
        brace = text.rfind("{", 0, search_end)
        if brace == -1:
            break
        try:
            obj, end = json.JSONDecoder().raw_decode(text[brace:])
        except json.JSONDecodeError:
            repaired = _repair_broken_top_level_object(text[brace:])
            try:
                obj = json.loads(repaired)
            except json.JSONDecodeError:
                search_end = brace
                continue
            meta = _canonical_json_string(obj)
            display = text[:brace].rstrip()
            return display, meta
        if brace + end == len(text):
            meta = _canonical_json_string(obj)
            display = text[:brace].rstrip()
            return display, meta
        search_end = brace

    first_brace = text.find("{")
    if first_brace != -1:
        repaired = _repair_broken_top_level_object(text[first_brace:])
        try:
            obj = json.loads(repaired)
        except json.JSONDecodeError:
            return raw, None
        meta = _canonical_json_string(obj)
        display = text[:first_brace].rstrip()
        return display, meta

    return raw, None

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
