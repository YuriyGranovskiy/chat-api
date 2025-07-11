# app/services.py
from flask import Blueprint
from app.models import Message, Chat, db, DoesNotExistError
from sqlalchemy import desc
from ulid import ulid
import ollama

bp = Blueprint('services', __name__)

def create_message(chat_id, message, sender_type):
    chat = Chat.query.get(chat_id)
    if not chat:
        raise DoesNotExistError
    new_message = Message(id=str(ulid()), chat_id=chat_id, sender_type=sender_type, message=message)
    db.session.add(new_message)
    db.session.commit()
    return new_message.id

def get_messages(chat_id, last_message_id=None, limit=10):
    chat = Chat.query.get(chat_id)
    if not chat:
        raise DoesNotExistError
    if last_message_id:
        messages = Message.query.filter_by(chat_id=chat_id).filter(Message.id <= last_message_id).order_by(desc(Message.id)).limit(limit).all()
    else:
        messages = Message.query.filter_by(chat_id=chat_id).order_by(desc(Message.id)).limit(limit).all()
    message_list = [{'id': m.id, 'message': m.message, 'sender_type': m.sender_type.name.lower()} for m in messages]
    return message_list