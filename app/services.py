from __future__ import annotations

import os
import secrets
from typing import Any, TypeVar

import ulid
from flask import current_app
from flask_jwt_extended import create_access_token
from sqlalchemy import desc
from werkzeug.datastructures import FileStorage

from app.assistant_message_parse import (
    assistant_display_for_client,
    split_assistant_content,
)
from app.chat_strategies import validate_strategy_id_for_create
from app.models import (
    Chat,
    DoesNotExistError,
    Location,
    Message,
    MessageType,
    Persona,
    Status,
    User,
    World,
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
    return [
        {
            "id": chat.id,
            "user_id": chat.user_id,
            "name": chat.name,
            "strategy_id": chat.strategy_id,
        }
        for chat in chats
    ]


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


def _safe_unlink(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _mime_from_magic(data: bytes) -> str | None:
    if len(data) >= 3 and data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 8 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 6 and (data.startswith(b"GIF87a") or data.startswith(b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _resolve_image_mime(file_storage: FileStorage, data: bytes) -> str | None:
    raw = (file_storage.mimetype or "").split(";")[0].strip().lower()
    allowed: frozenset[str] = current_app.config["ALLOWED_IMAGE_MIMES"]
    if raw in allowed:
        return raw
    magic = _mime_from_magic(data)
    if magic in allowed:
        return magic
    return None


def _allocate_image_token() -> str:
    for _ in range(32):
        token = secrets.token_urlsafe(32)
        taken = (
            World.query.filter_by(image_access_token=token).first() is not None
            or Persona.query.filter_by(image_access_token=token).first() is not None
            or Location.query.filter_by(image_access_token=token).first() is not None
        )
        if not taken:
            return token
    raise RuntimeError("Could not allocate a unique image token")


def _remove_stored_image(entity: Any) -> None:
    rel = getattr(entity, "image_path", None)
    if not rel:
        return
    path = os.path.join(current_app.config["MEDIA_ROOT"], rel)
    _safe_unlink(path)


def set_entity_image(model: type[ModelT], entity_id: str, file_storage: FileStorage) -> None:
    entity = model.query.get(entity_id)
    if not entity:
        raise DoesNotExistError
    if not file_storage or not file_storage.filename:
        raise ValueError("No file")

    data = file_storage.read()
    if not data:
        raise ValueError("Empty file")
    max_bytes: int = current_app.config["MAX_IMAGE_BYTES"]
    if len(data) > max_bytes:
        raise ValueError("File too large")

    mime = _resolve_image_mime(file_storage, data)
    if not mime:
        raise ValueError("Unsupported image type")

    mime_to_ext: dict[str, str] = current_app.config["MIME_TO_EXT"]
    ext = mime_to_ext[mime]
    media_root: str = current_app.config["MEDIA_ROOT"]

    old_path = getattr(entity, "image_path", None)
    if not entity.image_access_token:
        entity.image_access_token = _allocate_image_token()

    rel_path = f"{entity.image_access_token}{ext}"
    abs_path = os.path.join(media_root, rel_path)

    if old_path and old_path != rel_path:
        _safe_unlink(os.path.join(media_root, old_path))

    with open(abs_path, "wb") as f:
        f.write(data)

    entity.image_path = rel_path
    db.session.commit()


def clear_entity_image(model: type[ModelT], entity_id: str) -> None:
    entity = model.query.get(entity_id)
    if not entity:
        raise DoesNotExistError
    _remove_stored_image(entity)
    entity.image_path = None
    entity.image_access_token = None
    db.session.commit()


def resolve_media_file(token: str) -> tuple[str, str] | None:
    mime_to_ext: dict[str, str] = current_app.config["MIME_TO_EXT"]
    ext_to_mime = {v: k for k, v in mime_to_ext.items()}

    for model_cls in (World, Persona, Location):
        entity = model_cls.query.filter_by(image_access_token=token).first()
        if entity and entity.image_path:
            root: str = current_app.config["MEDIA_ROOT"]
            abs_path = os.path.join(root, entity.image_path)
            if not os.path.isfile(abs_path):
                return None
            ext = os.path.splitext(entity.image_path)[1].lower()
            mime = ext_to_mime.get(ext, "application/octet-stream")
            return abs_path, mime
    return None


def delete_entity(model: type[ModelT], entity_id: str) -> None:
    entity = model.query.get(entity_id)
    if not entity:
        raise DoesNotExistError
    _remove_stored_image(entity)
    db.session.delete(entity)
    db.session.commit()


def create_user_chat(
    user_id: str,
    name: str,
    world_id: str | None = None,
    profile_id: str | None = None,
    persona_ids: list[str] | None = None,
    location_ids: list[str] | None = None,
    strategy_id: str = "rpg",
) -> str:
    resolved_strategy = validate_strategy_id_for_create(strategy_id)
    new_chat = Chat(
        user_id=user_id,
        name=name,
        world_id=world_id,
        profile_id=profile_id,
        strategy_id=resolved_strategy,
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
