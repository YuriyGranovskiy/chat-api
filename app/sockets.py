import functools
from flask import request
from flask_socketio import emit, join_room, disconnect
from flask_jwt_extended import decode_token, get_jwt_identity
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.services import create_message, get_messages, is_user_in_chat, delete_message, regenerate_message, edit_message
from app.models import MessageType, Message, DoesNotExistError

session = {}

def register_socket_handlers(socketio_app):

    def authenticated_only(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                emit('error', {'message': 'Authentication required. Please connect with a valid token.'})
                disconnect()
            else:
                return f(*args, **kwargs)
        return wrapped

    @socketio_app.on('connect')
    def handle_connect(auth):
        if not auth or 'token' not in auth:
            print(f"Client {request.sid} connected without token. Disconnecting.")
            return False

        token = auth['token']
        try:
            decoded_token = decode_token(token)
            user_id = decoded_token['sub']
            
            session['user_id'] = user_id
            print(f"Client {request.sid} connected and authenticated as user {user_id}")
            
        except (ExpiredSignatureError, InvalidTokenError) as e:
            print(f"Client {request.sid} provided an invalid token: {e}. Disconnecting.")
            return False
        except Exception as e:
            print(f"An unexpected error occurred during connect: {e}")
            return False


    @socketio_app.on('disconnect')
    def handle_disconnect():
        user_id = session.get('user_id', 'Unknown')
        print(f"Client {request.sid} (User: {user_id}) disconnected")

    @socketio_app.on('join_chat')
    @authenticated_only
    def handle_join_chat(data):
        user_id = session['user_id']
        chat_id = data.get('chat_id')
        
        if not chat_id:
            return emit('error', {'message': 'chat_id is required'})

        if not is_user_in_chat(user_id, chat_id):
            return emit('error', {'message': 'Access denied'})

        join_room(chat_id)
        print(f"User {user_id} ({request.sid}) joined chat room: {chat_id}")
        for message in get_messages(chat_id):
            emit('new_message', message, room=chat_id)
        
        emit('status', {'message': f'Successfully joined chat {chat_id}'}) 

    @socketio_app.on('send_message')
    @authenticated_only
    def handle_send_message(data):
        user_id = session['user_id']
        chat_id = data.get('chat_id')
        message_content = data.get('message')

        if not chat_id or not message_content:
            return emit('error', {'message': 'Invalid message format'})

        if not is_user_in_chat(user_id, chat_id):
            return emit('error', {'message': 'Access denied'})

        message_id = create_message(chat_id, message_content, sender_type=MessageType.USER)
        
        message_data = {
            'id': str(message_id),
            'sender_type': 'user',
            'sender_id': user_id,
            'message': message_content
        }
        socketio_app.emit('new_message', message_data, room=chat_id)

    @socketio_app.on('delete_message')
    @authenticated_only
    def handle_delete_message(data):
        user_id = session['user_id']
        message_id = data.get('message_id')
        if not message_id:
            return emit('error', {'message': 'message_id is required'})
        message = Message.query.get(message_id)
        if not message:
            return emit('error', {'message': 'Message not found'})
        chat_id = message.chat_id
        if not is_user_in_chat(user_id, chat_id):
            return emit('error', {'message': 'Access denied'})
        try:
            delete_message(message_id)
            emit('message_deleted', {'message_id': message_id}, room=chat_id)
        except DoesNotExistError:
            emit('error', {'message': 'Message not found'})

    @socketio_app.on('regenerate_message')
    @authenticated_only
    def handle_regenerate_message(data):
        user_id = session['user_id']
        message_id = data.get('message_id')
        if not message_id:
            return emit('error', {'message': 'message_id is required'})
        message = Message.query.get(message_id)
        if not message or message.sender_type != MessageType.ASSISTANT:
            return emit('error', {'message': 'Message not found or not assistant type'})
        chat_id = message.chat_id
        if not is_user_in_chat(user_id, chat_id):
            return emit('error', {'message': 'Access denied'})
        try:
            deleted_ids, user_msg_id = regenerate_message(message_id)
            for mid in deleted_ids:
                emit('message_deleted', {'message_id': mid}, room=chat_id)
            emit('status_updated', {'message_id': user_msg_id, 'status': 'new'}, room=chat_id)
        except DoesNotExistError:
            emit('error', {'message': 'Regeneration failed'})

    @socketio_app.on('edit_message')
    @authenticated_only
    def handle_edit_message(data):
        user_id = session['user_id']
        message_id = data.get('message_id')
        new_text = data.get('message')
        if not message_id or new_text is None:
            return emit('error', {'message': 'message_id and message are required'})
        message = Message.query.get(message_id)
        if not message:
            return emit('error', {'message': 'Message not found'})
        chat_id = message.chat_id
        if not is_user_in_chat(user_id, chat_id):
            return emit('error', {'message': 'Access denied'})
        try:
            edit_message(message_id, new_text)
            emit('message_edited', {'message_id': message_id, 'message': new_text}, room=chat_id)
        except DoesNotExistError:
            emit('error', {'message': 'Edit failed'})
