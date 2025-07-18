import logging
import os

from flask import Flask, current_app
from flask_cors import CORS
from flask_socketio import SocketIO

from app.config import Config
from app.extensions import db, bcrypt, jwt
from app.message_job import process_messages
from app.sockets import register_socket_handlers

logger = logging.getLogger(__name__)

def create_app():
    def process_messages_background_task():
        logger.info(f'Background task started!')
        while True:
            with app.app_context():
                process_messages(socketio)
            socketio.sleep(1)

    app = Flask(__name__)
    CORS(app)
    socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")
    config = Config()
    app.config.from_object(config)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    
    # Регистрация Blueprint и создание таблиц
    from app.routes import bp as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')
    register_socket_handlers(socketio)

    with app.app_context():
        db.create_all()

    # Запуск фоновой задачи (если нужно, логику можно оставить здесь)
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        logger.info('Starting background task in the main worker process...')
        socketio.start_background_task(target=process_messages_background_task)
            
    return app, socketio
