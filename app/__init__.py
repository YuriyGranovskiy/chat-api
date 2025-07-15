import logging
import os
from flask import Flask, Blueprint
from flask_socketio import SocketIO
from app.config import Config
from app.routes import bp
from app.models import db
from app.message_job import process_messages
from app.sockets import register_socket_handlers

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
config = Config()
app.config.from_object(config)
logger = logging.getLogger(__name__)

def process_messages_background_task():
    logger.info(f'Background task started!')
    while True:
        with app.app_context():
            process_messages(socketio)
        socketio.sleep(1)

db.init_app(app)
with app.app_context():
    db.create_all()

app.register_blueprint(bp, url_prefix='/api')
register_socket_handlers(socketio)

if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    logger.info('Starting background task in the main worker process...')
    socketio.start_background_task(target=process_messages_background_task)
