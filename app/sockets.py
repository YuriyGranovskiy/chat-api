from app.models import MessageType
from app.services import create_message, get_messages
from flask_socketio import emit, join_room, disconnect, rooms
from flask import request

active_chat_info = {} 

def register_socket_handlers(socketio_app):
    @socketio_app.on('connect')
    def handle_connect():
        print(f"Client connected: {request.sid}")

    @socketio_app.on('disconnect')
    def handle_disconnect():
        print(f"Client disconnected: {request.sid}")

        for chat_id, info in list(active_chat_info.items()):
            pass

    @socketio_app.on('join_chat')
    def handle_join_chat(data):
        chat_id = data.get('chat_id')
        if not chat_id:
            emit('error', {'message': 'chat_id is required'})
            return

        join_room(chat_id)
        print(f"Client {request.sid} joined chat room: {chat_id}")
        
        if chat_id not in active_chat_info:
            active_chat_info[chat_id] = {'task': None, 'connections_count': 0}
        
        for message in get_messages(chat_id):
            emit('new_message', message, room=chat_id)

        emit('status', {'message': f'Successfully joined chat {chat_id}'}) 

    @socketio_app.on('leave_chat')
    def handle_leave_chat(data):
        chat_id = data.get('chat_id')
        if not chat_id:
            emit('error', {'message': 'chat_id is required'})
            return
        
        if chat_id in active_chat_info:
            active_chat_info[chat_id]['connections_count'] -= 1
            if active_chat_info[chat_id]['connections_count'] <= 0:
                pass # Задача сама остановится
        
        emit('status', {'message': f'Left chat {chat_id}'}, room=request.sid)

        print(f"Client {request.sid} explicitly left chat room: {chat_id}")

    @socketio_app.on('send_message')
    def handle_send_message(data):
        """
        Обработка входящего сообщения от клиента через WebSocket.
        Ожидаем data = {'chat_id': '...', 'user_id': '...', 'message': '...'}
        """
        chat_id = data.get('chat_id')
        message_content = data.get('message')

        if not chat_id or not message_content:
            emit('error', {'message': 'Invalid message format (requires chat_id, message)'})
            return

        message_id = create_message(chat_id, message_content, sender_type=MessageType.USER)        
        message_data = {
            'id': str(message_id),
            'sender_type': 'user',
            'message': message_content
        }

        socketio_app.emit('new_message', message_data, room=chat_id, include_self=True)
        print(f"User message sent to chat {chat_id}: {message_content}")
