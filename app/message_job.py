from __future__ import annotations

import logging
import logging.config
from functools import lru_cache
from typing import Any

import ollama
from sqlalchemy import asc, update

from app.assistant_message_parse import (
    assistant_raw_for_model,
    split_assistant_content,
)
from app.chat_strategies import get_strategy
from app.logging_config import get_logging_config
from app.models import Chat, Message, MessageType, Status, db, get_ulid

logging.config.dictConfig(get_logging_config())
logger = logging.getLogger(__name__)

OLLAMA_OPTIONS: dict[str, Any] = {
    "temperature": 0.85,
    "top_p": 0.9,
    "num_ctx": 65536,
    "repeat_penalty": 1.2,
}


@lru_cache(maxsize=1)
def _tokenizer() -> Any:
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        "hf-internal-testing/llama-tokenizer",
        local_files_only=True,
    )


def _messages_for_model(chat: Chat) -> list[dict[str, str]]:
    strategy = get_strategy(chat.strategy_id)
    chat_messages = Message.query.filter_by(chat_id=chat.id).order_by(asc(Message.id)).all()
    model_messages = [{"role": "system", "content": strategy.build_system_prompt(chat)}]

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
        chat_id = chat.id
        strategy = get_strategy(chat.strategy_id)
        messages = _messages_for_model(chat)
        pending_user_messages = Message.query.filter_by(
            chat_id=chat_id,
            sender_type=MessageType.USER,
            status=Status.NEW,
        ).all()

        pending_ids = [m.id for m in pending_user_messages]
        if not pending_ids:
            continue

        try:
            logger.info("Processing chat %s with %s messages", chat_id, len(messages))
            result = ollama.chat(
                model="ministral-3:8b",
                messages=messages,
                options=OLLAMA_OPTIONS,
            )
            content = result["message"]["content"]
            display_text, meta = split_assistant_content(content)
            display_text, meta = strategy.refine_assistant_output(chat, display_text, meta)
            processed_message_id = get_ulid()
            assistant_message = Message(
                id=processed_message_id,
                chat_id=chat_id,
                sender_type=MessageType.ASSISTANT,
                message=display_text,
                assistant_meta=meta,
                status=Status.PROCESSED,
            )
            db.session.add(assistant_message)
            db.session.execute(
                update(Message)
                .where(
                    Message.id.in_(pending_ids),
                    Message.chat_id == chat_id,
                    Message.sender_type == MessageType.USER,
                    Message.status == Status.NEW,
                )
                .values(status=Status.PROCESSED),
            )

            db.session.commit()
            socketio_app.emit(
                "new_message",
                {
                    "id": processed_message_id,
                    "message": display_text,
                    "sender_type": "assistant",
                    "assistant_meta": meta,
                    "has_speech": False,
                },
                room=chat_id,
                include_self=True,
            )
            logger.info(
                "Chat %s processed successfully. Tokens sent: %s",
                chat_id,
                count_tokens(messages),
            )
        except Exception:
            db.session.rollback()
            logger.exception("Failed to process chat %s", chat_id)


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
