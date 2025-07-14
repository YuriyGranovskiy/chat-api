from flask import Flask, Blueprint
from flask_socketio import SocketIO
from app.config import Config
from app.routes import bp
from app.models import db
from app.message_job import process_messages
from app.sockets_mock import register_socket_handlers
from asyncio import run, sleep, new_event_loop, set_event_loop
from asyncio import sleep
from datetime import datetime
from threading import Thread

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
config = Config()
app.config.from_object(config)

print(__name__)

def start_async_job():
    loop = new_event_loop()
    set_event_loop(loop)
    loop.run_until_complete(process_messages_job())

def run_background_job():
    t = Thread(target=start_async_job)
    t.daemon = True
    t.start()

async def process_messages_job():
    while True:
        with app.app_context():
            process_messages()
        await sleep(1)

register_socket_handlers(socketio)

if __name__ == 'app':
    db.init_app(app)
    with app.app_context():
        db.create_all()
    app.register_blueprint(bp, url_prefix='/api')
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    run_background_job()