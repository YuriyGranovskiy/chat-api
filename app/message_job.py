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

rules = (
    "1. Respond with TWO SHORT paragraphs ONLY.\n"
    "2. Each paragraph must be exactly 2-3 sentences long.\n"
    "3. Be extremely concise. Avoid purple prose and long metaphors.\n"
    "4. Use 'Actions' and \"Speech\" format.\n"
    "5. Stop immediately after the second paragraph."
)

def process_messages(socketio_app):
    chats_with_new_user_messages = Chat.query.join(Message, Message.chat_id == Chat.id).filter_by(sender_type=MessageType.USER, status=Status.NEW).distinct().all()

    for chat in chats_with_new_user_messages:
        new_messages = Message.query.filter_by(chat_id=chat.id).order_by(asc(Message.id)).all()
        persona = chat.person_description or "A mysterious stranger."
        scenario = chat.scenario or "In a quiet room."

        system_content = (
            f"### YOUR NAME:\n{chat.person_name}\n\n"
            f"### YOUR ROLE:\n{persona}\n\n"
            f"### CURRENT SCENARIO:\n{scenario}\n\n"
            f"### MANDATORY RESPONSE FORMATTING RULES:\n{rules}"
        )
        
        messages = [{"role": "system", "content": system_content}]

        for message in new_messages:
            if message.sender_type == MessageType.SYSTEM:
                continue 
    
            role = "assistant" if message.sender_type == MessageType.ASSISTANT else "user"
            messages.append({"role": role, "content": message.message})            

        if messages[-1]["role"] == "user":
                        messages[-1]["content"] += "\n\n(Remember: 2 short paragraphs, 2-3 short sentences each, *actions* and \"speech\")"
        try:
            logger.info(messages)
            result = ollama.chat(
                model="ministral-3:8b", 
                messages=messages,
                options={
                    "temperature": 0.85,
                    "top_p": 0.9,
                    "num_ctx": 65536,
                    "repeat_penalty": 1.2
                }
            )
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
