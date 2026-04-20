from __future__ import annotations

from typing import Any, TypeVar

import ulid
from flask_jwt_extended import create_access_token
from sqlalchemy import desc

from app.assistant_message_parse import (
    assistant_display_for_client,
    split_assistant_content,
)
from app.models import (
    Chat,
    DoesNotExistError,
    Location,
    Message,
    MessageType,
    Persona,
    Status,
    User,
    db,
)

ModelT = TypeVar("ModelT")


def register_user(username: str, password: str) -> str:
    if User.query.filter_by(username=username).first():
        raise ValueError("User with this username already exists")

    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return create_access_token(identity=new_user.id)


def login_user(username: str, password: str) -> str | None:
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return create_access_token(identity=user.id)
    return None


def get_user_chats(user_id: str) -> list[dict[str, str]]:
    chats = Chat.query.filter_by(user_id=user_id).all()
    return [{"id": chat.id, "user_id": chat.user_id, "name": chat.name} for chat in chats]


def message_text_for_client(message: Message) -> str:
    if message.sender_type == MessageType.ASSISTANT:
        return assistant_display_for_client(message.message, message.assistant_meta)
    return message.message


def create_message(chat_id: str, message: str, sender_type: MessageType) -> str:
    chat = Chat.query.get(chat_id)
    if not chat:
        raise DoesNotExistError

    assistant_meta: str | None = None
    body = message
    if sender_type == MessageType.ASSISTANT:
        body, assistant_meta = split_assistant_content(message)

    new_message = Message(
        id=str(ulid.new()),
        chat_id=chat_id,
        sender_type=sender_type,
        message=body,
        assistant_meta=assistant_meta,
    )
    db.session.add(new_message)
    db.session.commit()
    return new_message.id


def get_messages(
    chat_id: str,
    last_message_id: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    chat = Chat.query.get(chat_id)
    if not chat:
        raise DoesNotExistError

    base_query = Message.query.filter_by(chat_id=chat_id).order_by(desc(Message.id))
    if last_message_id:
        base_query = base_query.filter(Message.id <= last_message_id)
    messages = base_query.limit(limit).all()

    return [
        {
            "id": message.id,
            "message": message_text_for_client(message),
            "sender_type": message.sender_type.name.lower(),
            "assistant_meta": message.assistant_meta,
        }
        for message in messages
    ]


def is_user_in_chat(user_id: str, chat_id: str) -> bool:
    return Chat.query.filter_by(id=chat_id, user_id=user_id).first() is not None


def delete_chat(chat_id: str) -> None:
    chat = Chat.query.get(chat_id)
    if not chat:
        raise DoesNotExistError

    for message in Message.query.filter_by(chat_id=chat_id).all():
        db.session.delete(message)
    db.session.delete(chat)
    db.session.commit()


def delete_message(message_id: str) -> None:
    message = Message.query.get(message_id)
    if not message:
        raise DoesNotExistError
    db.session.delete(message)
    db.session.commit()


def regenerate_message(message_id: str) -> tuple[list[str], str]:
    message = Message.query.get(message_id)
    if not message or message.sender_type != MessageType.ASSISTANT:
        raise DoesNotExistError

    messages = Message.query.filter_by(chat_id=message.chat_id).order_by(Message.id).all()
    index = next((i for i, item in enumerate(messages) if item.id == message_id), None)
    if index is None:
        raise DoesNotExistError

    previous_user_message = next(
        (item for item in reversed(messages[:index]) if item.sender_type == MessageType.USER),
        None,
    )
    if previous_user_message is None:
        raise DoesNotExistError

    messages_to_delete = messages[index:]
    deleted_ids = [item.id for item in messages_to_delete]
    for item in messages_to_delete:
        db.session.delete(item)

    previous_user_message.status = Status.NEW
    db.session.commit()
    return deleted_ids, previous_user_message.id


def edit_message(message_id: str, new_text: str) -> str:
    message = Message.query.get(message_id)
    if not message:
        raise DoesNotExistError
    if message.sender_type == MessageType.ASSISTANT:
        body, assistant_meta = split_assistant_content(new_text)
        message.message = body
        message.assistant_meta = assistant_meta
    else:
        message.message = new_text
    db.session.commit()
    return message.id


def create_entity(model: type[ModelT], **kwargs: Any) -> ModelT:
    entity = model(**kwargs)
    db.session.add(entity)
    db.session.commit()
    return entity


def update_entity(model: type[ModelT], entity_id: str, **kwargs: Any) -> ModelT:
    entity = model.query.get(entity_id)
    if not entity:
        raise DoesNotExistError

    for key, value in kwargs.items():
        if hasattr(entity, key):
            setattr(entity, key, value)
    db.session.commit()
    return entity


def get_entities(model: type[ModelT]) -> list[ModelT]:
    return model.query.all()


def delete_entity(model: type[ModelT], entity_id: str) -> None:
    entity = model.query.get(entity_id)
    if not entity:
        raise DoesNotExistError
    db.session.delete(entity)
    db.session.commit()


def create_user_chat(
    user_id: str,
    name: str,
    world_id: str | None = None,
    profile_id: str | None = None,
    persona_ids: list[str] | None = None,
    location_ids: list[str] | None = None,
) -> str:
    new_chat = Chat(
        user_id=user_id,
        name=name,
        world_id=world_id,
        profile_id=profile_id,
    )

    if persona_ids:
        new_chat.personas.extend(Persona.query.filter(Persona.id.in_(persona_ids)).all())
    if location_ids:
        new_chat.available_locations.extend(
            Location.query.filter(Location.id.in_(location_ids)).all()
        )

    db.session.add(new_chat)
    db.session.commit()
    return new_chat.id


def add_persona_to_chat(chat_id: str, persona_id: str) -> None:
    chat = Chat.query.get(chat_id)
    persona = Persona.query.get(persona_id)
    if not chat or not persona:
        raise DoesNotExistError
    if persona not in chat.personas:
        chat.personas.append(persona)
        db.session.commit()
