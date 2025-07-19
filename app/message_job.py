from app.logging_config import get_logging_config
from app.models import Message, Status, db, MessageType, Chat
from sqlalchemy import asc
from ulid import ulid
import ollama
import json
import logging.config
from transformers import AutoTokenizer
from datetime import datetime

logging_config = logging.config.dictConfig(get_logging_config())
logger = logging.getLogger(__name__)

def process_messages(socketio_app):
    chats_with_new_user_messages = Chat.query.join(Message, Message.chat_id == Chat.id).filter_by(sender_type=MessageType.USER, status=Status.NEW).distinct().all()

    for chat in chats_with_new_user_messages:
        new_messages = Message.query.filter_by(chat_id=chat.id).order_by(asc(Message.id)).all()
        messages = []
        for message in new_messages:
            if message.sender_type == MessageType.SYSTEM:
                role = "system"
            elif message.sender_type == MessageType.ASSISTANT:
                role = "assistant"
            else:
                role = "user"

            messages.append({
                "role": role,
                "content": message.message
            })

        try:
            logger.info(messages)
            result = ollama.chat(model="llama3.2", messages=messages)
            processed_message_id = str(ulid())
            new_processed_message = Message(id=processed_message_id, chat_id=message.chat_id, sender_type="ASSISTANT", message=result["message"]["content"], status=Status.PROCESSED)
            db.session.add(new_processed_message)
            message.status = Status.PROCESSED
            db.session.commit()
            socketio_app.emit("new_message", {"id": processed_message_id, "message": result["message"]["content"], "sender_type": "assistant"}, room=message.chat.id, include_self=True)

            logger.info(f"Message {message.id} sccessfully processed and added to the database. Tokens sent {count_tokens(messages)}")
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {str(e)}")

def count_tokens(messages):
    tokenizer = AutoTokenizer.from_pretrained("hf-internal-testing/llama-tokenizer")
    total = 0
    for m in messages:
        role = m["role"]
        content = m["content"]
        role_tokens = tokenizer.encode(role, add_special_tokens=False)
        content_tokens = tokenizer.encode(content, add_special_tokens=False)
        total += len(role_tokens) + len(content_tokens)
    return total
