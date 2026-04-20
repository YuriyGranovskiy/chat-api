from __future__ import annotations

import json
import logging
import logging.config
import re
from functools import lru_cache
from typing import Any

import ollama
from sqlalchemy import asc
from transformers import AutoTokenizer
import ulid

from app.assistant_message_parse import (
    assistant_raw_for_model,
    split_assistant_content,
)
from app.logging_config import get_logging_config
from app.models import Chat, Location, Message, MessageType, Status, db

logging.config.dictConfig(get_logging_config())
logger = logging.getLogger(__name__)

rules = (
    "1. Respond with TWO SHORT paragraphs ONLY.\n"
    "2. Each paragraph must be exactly 2-3 sentences long.\n"
    "3. Be extremely concise. Avoid purple prose and long metaphors.\n"
    "4. Format actions in asterisks and speech in quotes.\n"
    "5. After the second paragraph output scene JSON strictly with keys: "
    "\"location\" (string), \"persons\" (names present in the scene), "
    "\"location_description\" (short location description, only interior, no descriotion of the persons), "
    "\"clothing\" and \"ammunition\" (objects mapping each name in persons to a short string). "
    "Use empty string or omit a name if unknown; use empty objects {} if no weapons apply. "
    "Example: {\"location\": \"...\", \"location_description\": \"...\", \"persons\": [\"A\"], "
    "\"clothing\": {\"A\": \"...\"}, \"ammunition\": {\"A\": \"...\"}}.\n"
    "Fill location_description only if the location is new.\n"
    "6. When the user speaks to a specific personas, respond as them.\n"
    "7. Prefix persona's speech with their name, e.g., AKIRA: \"...\"\n\n"
)

OLLAMA_OPTIONS: dict[str, Any] = {
    "temperature": 0.85,
    "top_p": 0.9,
    "num_ctx": 65536,
    "repeat_penalty": 1.2,
}


@lru_cache(maxsize=1)
def _tokenizer() -> AutoTokenizer:
    return AutoTokenizer.from_pretrained(
        "hf-internal-testing/llama-tokenizer",
        local_files_only=True,
    )


def _new_ulid() -> str:
    return str(ulid.new())


def _normalize_location_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def _find_location_by_normalized_name(normalized_name: str) -> Location | None:
    target = normalized_name.casefold()
    for location in Location.query.all():
        if _normalize_location_name(location.name).casefold() == target:
            return location
    return None


def _sync_location_from_meta(chat: Chat, meta: str | None) -> str | None:
    if not meta:
        return meta

    parsed_meta = json.loads(meta)
    raw_location = parsed_meta.get("location")
    if not isinstance(raw_location, str):
        parsed_meta.pop("new_location", None)
        return json.dumps(parsed_meta, ensure_ascii=False, sort_keys=True)

    normalized_location_name = _normalize_location_name(raw_location)
    if not normalized_location_name:
        parsed_meta.pop("new_location", None)
        return json.dumps(parsed_meta, ensure_ascii=False, sort_keys=True)

    parsed_meta["location"] = normalized_location_name

    location_description = parsed_meta.get("location_description")
    location_description_text = (
        location_description.strip()
        if isinstance(location_description, str) and location_description.strip()
        else None
    )
    if location_description_text:
        parsed_meta["location_description"] = location_description_text

    location = _find_location_by_normalized_name(normalized_location_name)
    location_is_new = False
    if location is None:
        location = Location(
            name=normalized_location_name,
            description=location_description_text,
        )
        db.session.add(location)
        location_is_new = True
    elif location_description_text and not location.description:
        location.description = location_description_text

    if location not in chat.available_locations:
        chat.available_locations.append(location)

    if location_is_new:
        parsed_meta["new_location"] = {
            "name": location.name,
            "description": location.description or "",
        }
    else:
        parsed_meta.pop("new_location", None)

    return json.dumps(parsed_meta, ensure_ascii=False, sort_keys=True)


def _build_chat_context(chat: Chat) -> str:
    personas_block = (
        "\n".join(
            f"{persona.name}: {persona.description or 'No description'}"
            for persona in chat.personas
        )
        or "No personas in this chat."
    )
    locations_block = (
        "\n".join(
            f"{location.name}: {location.description or 'No description'}"
            for location in chat.available_locations
        )
        or "No locations in this chat."
    )
    scenario = chat.scenario or "In a quiet room."

    return (
        "### RPG ENGINE MODE\n"
        "You are the Game Master and the narrator. "
        "You control the environment and all NPCs.\n\n"
        f"### CURRENT SCENARIO:\n{scenario}\n\n"
        f"### CHAT PERSONAS (name: description):\n{personas_block}\n\n"
        f"### CHAT LOCATIONS (name: description):\n{locations_block}\n\n"
        f"### MANDATORY RESPONSE FORMATTING RULES:\n{rules}"
    )


def _messages_for_model(chat: Chat) -> list[dict[str, str]]:
    chat_messages = Message.query.filter_by(chat_id=chat.id).order_by(asc(Message.id)).all()
    model_messages = [{"role": "system", "content": _build_chat_context(chat)}]

    for chat_message in chat_messages:
        if chat_message.sender_type == MessageType.SYSTEM:
            continue
        role = (
            "assistant"
            if chat_message.sender_type == MessageType.ASSISTANT
            else "user"
        )
        if chat_message.sender_type == MessageType.ASSISTANT:
            content = assistant_raw_for_model(
                chat_message.message,
                chat_message.assistant_meta,
            )
        else:
            content = chat_message.message
        model_messages.append({"role": role, "content": content})

    return model_messages


def process_messages(socketio_app: Any) -> None:
    chats = (
        Chat.query.join(Message, Message.chat_id == Chat.id)
        .filter_by(sender_type=MessageType.USER, status=Status.NEW)
        .distinct()
        .all()
    )

    for chat in chats:
        messages = _messages_for_model(chat)
        pending_user_messages = Message.query.filter_by(
            chat_id=chat.id,
            sender_type=MessageType.USER,
            status=Status.NEW,
        ).all()

        try:
            logger.info("Processing chat %s with %s messages", chat.id, len(messages))
            result = ollama.chat(
                model="ministral-3:8b",
                messages=messages,
                options=OLLAMA_OPTIONS,
            )
            content = result["message"]["content"]
            display_text, meta = split_assistant_content(content)
            meta = _sync_location_from_meta(chat, meta)
            processed_message_id = _new_ulid()
            assistant_message = Message(
                id=processed_message_id,
                chat_id=chat.id,
                sender_type=MessageType.ASSISTANT,
                message=display_text,
                assistant_meta=meta,
                status=Status.PROCESSED,
            )
            db.session.add(assistant_message)
            for pending_message in pending_user_messages:
                pending_message.status = Status.PROCESSED

            db.session.commit()
            socketio_app.emit(
                "new_message",
                {
                    "id": processed_message_id,
                    "message": display_text,
                    "sender_type": "assistant",
                    "assistant_meta": meta,
                },
                room=chat.id,
                include_self=True,
            )
            logger.info(
                "Chat %s processed successfully. Tokens sent: %s",
                chat.id,
                count_tokens(messages),
            )
        except Exception:
            logger.exception("Failed to process chat %s", chat.id)


def count_tokens(messages: list[dict[str, str]]) -> int:
    try:
        tokenizer = _tokenizer()
    except Exception:
        logger.warning("Tokenizer unavailable, token counting skipped", exc_info=True)
        return 0

    total_tokens = 0
    for message in messages:
        role_tokens = tokenizer.encode(message["role"], add_special_tokens=False)
        content_tokens = tokenizer.encode(
            message["content"],
            add_special_tokens=False,
        )
        total_tokens += len(role_tokens) + len(content_tokens)
    return total_tokens
