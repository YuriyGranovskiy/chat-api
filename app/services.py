# app/services.py
from flask import Blueprint
from app.models import Message, Chat, db, DoesNotExistError, SendMessageType
from ulid import ulid

bp = Blueprint('services', __name__)

def create_message(chat_id, message):
    chat = Chat.query.get(chat_id)
    if not chat:
        raise DoesNotExistError
    new_message = Message(id=str(ulid()), chat_id=chat_id, sender_type=SendMessageType.USER, message=message)
    db.session.add(new_message)
    db.session.commit()
    return new_message.id

def get_messages(chat_id):
    chat = Chat.query.get(chat_id)
    if not chat:
        raise DoesNotExistError
    messages = Message.query.filter_by(chat_id=chat_id).all()
    message_list = [{'id': m.id, 'chat_id': m.chat_id, 'message': m.message, 'sender_type': m.sender_type.name} for m in messages]
    return message_list