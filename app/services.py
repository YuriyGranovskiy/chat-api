from flask import Blueprint
from flask_jwt_extended import create_access_token
from app.models import Message, Chat, MessageType, Status, User, db, DoesNotExistError
from sqlalchemy import desc
from ulid import ulid

bp = Blueprint('services', __name__)

def register_user(username, password):
    if User.query.filter_by(username=username).first():
        raise ValueError('User with this username already exists')

    new_user = User(username=username)
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    access_token = create_access_token(identity=new_user.id)
    return access_token

def login_user(username, password):
    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        access_token = create_access_token(identity=user.id)
        return access_token
    return None

def create_user_chat(user_id, name, initial_message):
    new_chat = Chat(user_id=user_id, name=name)
    db.session.add(new_chat)
    db.session.commit()
    create_message(new_chat.id, initial_message, MessageType.SYSTEM)
    return new_chat.id

def get_user_chats(user_id):
    chats = Chat.query.filter_by(user_id=user_id).all()
    return [{'id': c.id, 'user_id': c.user_id, 'name': c.name} for c in chats]

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

def is_user_in_chat(user_id, chat_id):
    chat = Chat.query.filter_by(id=chat_id, user_id=user_id).first()
    return chat is not None

def delete_chat(chat_id):
    chat = Chat.query.get(chat_id)
    if not chat:
        raise DoesNotExistError

    messages = Message.query.filter_by(chat_id=chat_id).all()
    for message in messages:
        db.session.delete(message)

    db.session.delete(chat)
    db.session.commit()

    return None

def delete_message(message_id):
    message = Message.query.get(message_id)
    if not message:
        raise DoesNotExistError
    db.session.delete(message)
    db.session.commit()
    return None

def regenerate_message(message_id):
    message = Message.query.get(message_id)
    if not message or message.sender_type != MessageType.ASSISTANT:
        raise DoesNotExistError
    chat_id = message.chat_id
    # Получаем все сообщения в чате по id (по возрастанию)
    messages = Message.query.filter_by(chat_id=chat_id).order_by(Message.id).all()
    # Найти индекс текущего сообщения
    idx = next((i for i, m in enumerate(messages) if m.id == message_id), None)
    if idx is None:
        raise DoesNotExistError
    # Найти предыдущее user-сообщение
    prev_user_msg = None
    for m in reversed(messages[:idx]):
        if m.sender_type == MessageType.USER:
            prev_user_msg = m
            break
    if not prev_user_msg:
        raise DoesNotExistError
    # Собрать id всех сообщений, которые будут удалены (от текущего и далее)
    to_delete = [m for m in messages[idx:]]
    deleted_ids = [m.id for m in to_delete]
    for m in to_delete:
        db.session.delete(m)
    # Обновить статус предыдущего user-сообщения
    prev_user_msg.status = Status.NEW
    db.session.commit()
    return deleted_ids, prev_user_msg.id
