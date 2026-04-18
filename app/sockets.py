import functools
import logging

from flask import request
from flask_jwt_extended import decode_token
from flask_socketio import disconnect, emit, join_room
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.models import DoesNotExistError, Message, MessageType
from app.services import (
    create_message,
    delete_message,
    edit_message,
    get_messages,
    is_user_in_chat,
    regenerate_message,
)

logger = logging.getLogger(__name__)
session_by_sid: dict[str, str] = {}


def register_socket_handlers(socketio_app):
    def authenticated_only(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if request.sid not in session_by_sid:
                emit(
                    "error",
                    {
                        "message": (
                            "Authentication required. "
                            "Please connect with a valid token."
                        )
                    },
                )
                disconnect()
                return None
            return f(*args, **kwargs)

        return wrapped

    @socketio_app.on("connect")
    def handle_connect(auth):
        if not auth or "token" not in auth:
            logger.warning("Client %s connected without token", request.sid)
            return False

        token = auth["token"]
        try:
            decoded_token = decode_token(token)
            user_id = decoded_token["sub"]
            session_by_sid[request.sid] = user_id
            logger.info(
                "Client %s connected and authenticated as user %s",
                request.sid,
                user_id,
            )
        except (ExpiredSignatureError, InvalidTokenError) as error:
            logger.warning(
                "Client %s provided invalid token: %s",
                request.sid,
                error,
            )
            return False
        except Exception:
            logger.exception("Unexpected error during socket connect")
            return False

    @socketio_app.on("disconnect")
    def handle_disconnect():
        user_id = session_by_sid.pop(request.sid, "Unknown")
        logger.info("Client %s (User: %s) disconnected", request.sid, user_id)

    @socketio_app.on("join_chat")
    @authenticated_only
    def handle_join_chat(data):
        user_id = session_by_sid[request.sid]
        chat_id = data.get("chat_id")

        if not chat_id:
            return emit("error", {"message": "chat_id is required"})

        if not is_user_in_chat(user_id, chat_id):
            return emit("error", {"message": "Access denied"})

        join_room(chat_id)
        logger.info("User %s (%s) joined chat room %s", user_id, request.sid, chat_id)
        for message in get_messages(chat_id):
            emit("new_message", message, room=chat_id)

        emit("status", {"message": f"Successfully joined chat {chat_id}"})

    @socketio_app.on("send_message")
    @authenticated_only
    def handle_send_message(data):
        user_id = session_by_sid[request.sid]
        chat_id = data.get("chat_id")
        message_content = data.get("message")

        if not chat_id or not message_content:
            return emit("error", {"message": "Invalid message format"})

        if not is_user_in_chat(user_id, chat_id):
            return emit("error", {"message": "Access denied"})

        message_id = create_message(chat_id, message_content, sender_type=MessageType.USER)

        message_data = {
            "id": str(message_id),
            "sender_type": "user",
            "sender_id": user_id,
            "message": message_content,
        }
        socketio_app.emit("new_message", message_data, room=chat_id)

    @socketio_app.on("delete_message")
    @authenticated_only
    def handle_delete_message(data):
        user_id = session_by_sid[request.sid]
        message_id = data.get("message_id")
        if not message_id:
            return emit("error", {"message": "message_id is required"})
        message = Message.query.get(message_id)
        if not message:
            return emit("error", {"message": "Message not found"})
        chat_id = message.chat_id
        if not is_user_in_chat(user_id, chat_id):
            return emit("error", {"message": "Access denied"})
        try:
            delete_message(message_id)
            emit("message_deleted", {"message_id": message_id}, room=chat_id)
        except DoesNotExistError:
            emit("error", {"message": "Message not found"})

    @socketio_app.on("regenerate_message")
    @authenticated_only
    def handle_regenerate_message(data):
        user_id = session_by_sid[request.sid]
        message_id = data.get("message_id")
        if not message_id:
            return emit("error", {"message": "message_id is required"})
        message = Message.query.get(message_id)
        if not message or message.sender_type != MessageType.ASSISTANT:
            return emit("error", {"message": "Message not found or not assistant type"})
        chat_id = message.chat_id
        if not is_user_in_chat(user_id, chat_id):
            return emit("error", {"message": "Access denied"})
        try:
            deleted_ids, user_msg_id = regenerate_message(message_id)
            for mid in deleted_ids:
                emit("message_deleted", {"message_id": mid}, room=chat_id)
            emit(
                "status_updated",
                {"message_id": user_msg_id, "status": "new"},
                room=chat_id,
            )
        except DoesNotExistError:
            emit("error", {"message": "Regeneration failed"})

    @socketio_app.on("edit_message")
    @authenticated_only
    def handle_edit_message(data):
        user_id = session_by_sid[request.sid]
        message_id = data.get("message_id")
        new_text = data.get("message")
        if not message_id or new_text is None:
            return emit("error", {"message": "message_id and message are required"})
        message = Message.query.get(message_id)
        if not message:
            return emit("error", {"message": "Message not found"})
        chat_id = message.chat_id
        if not is_user_in_chat(user_id, chat_id):
            return emit("error", {"message": "Access denied"})
        try:
            edit_message(message_id, new_text)
            emit(
                "message_edited",
                {"message_id": message_id, "message": new_text},
                room=chat_id,
            )
        except DoesNotExistError:
            emit("error", {"message": "Edit failed"})
