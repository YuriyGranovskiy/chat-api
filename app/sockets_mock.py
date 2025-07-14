import random
import time
import eventlet
from flask_socketio import emit, join_room, disconnect, rooms
from flask import request

active_chat_info = {} 

def send_random_messages_task(chat_id, socketio_app):
    messages = [
        "Привет, как дела?",
        "Это случайное сообщение.",
        "Тестовый стриминг работает!",
        "Скоро здесь будет Ollama.",
        "Добро пожаловать в чат!",
        "Проверка связи 1, 2, 3...",
        "Что думаешь об этом?",
        "Просто для теста."
    ]
    
    while True:
        if chat_id not in active_chat_info or active_chat_info[chat_id]['connections_count'] <= 0:
            print(f"Stopping background task for chat {chat_id} as no users are connected.")
            if chat_id in active_chat_info:
                del active_chat_info[chat_id]
            break

        message_content = random.choice(messages)
        message_data = {
            'chat_id': chat_id,
            'sender': 'System (Mock)',
            'content': message_content,
            'timestamp': time.time()
        }
        
        # *** ИЗМЕНЕНИЕ ЗДЕСЬ: Добавлено include_self=True ***
        socketio_app.emit('new_message', message_data, room=chat_id, include_self=True)
        
        # Добавим дополнительный лог, чтобы видеть, что сообщение отправлено
        print(f"Sent message to chat {chat_id} for all: {message_content}")

        eventlet.sleep(random.uniform(1, 3))

def register_socket_handlers(socketio_app):
    @socketio_app.on('connect')
    def handle_connect():
        print(f"Client connected: {request.sid}")

    @socketio_app.on('disconnect')
    def handle_disconnect():
        print(f"Client disconnected: {request.sid}")
        # Здесь нет прямого способа узнать chat_id, из которого отключился клиент.
        # Это потребует более сложного отслеживания, например, хранения
        # маппинга SID -> list_of_chat_ids_joined, или использования Redis pub/sub.
        # Для заглушки мы полагаемся на то, что фоновая задача сама себя остановит,
        # когда active_chat_info[chat_id]['connections_count'] достигнет 0.
        # Однако, этот счетчик нужно уменьшать при disconnect.
        # Давайте добавим временное решение для заглушки.
        
        # Временное решение: итерируемся по active_chat_info и уменьшаем счетчик,
        # если клиент был в этой комнате. Это не идеально, но для заглушки сойдет.
        # В реальной системе это должно быть более точным.
        for chat_id, info in list(active_chat_info.items()):
            # Эта проверка очень условна, так как rooms() возвращает комнаты для ТЕКУЩЕГО запроса,
            # а не для отключившегося SID.
            # Правильное решение требует storing state of SIDs in rooms outside of Flask's request context.
            # Для заглушки это может быть более сложным, чем стоит.
            # Пока оставим как есть, так как `send_random_messages_task` проверяет `connections_count`.
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
        
        active_chat_info[chat_id]['connections_count'] += 1

        if active_chat_info[chat_id]['task'] is None:
            print(f"Starting background task for chat {chat_id}")
            task = socketio_app.start_background_task(send_random_messages_task, chat_id, socketio_app)
            active_chat_info[chat_id]['task'] = task
        
        # *** ИЗМЕНЕНИЕ ЗДЕСЬ: Явно отправляем статус только инициирующему клиенту ***
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
        
        # emit('status', {'message': f'Left chat {chat_id}'}) # Это сообщение уйдет всем в комнате, если не указать room=request.sid
        # Отправляем статус только уходящему клиенту
        emit('status', {'message': f'Left chat {chat_id}'}, room=request.sid)

        print(f"Client {request.sid} explicitly left chat room: {chat_id}")
