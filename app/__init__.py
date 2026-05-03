import logging
import os

log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "log")
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger(__name__)


def create_app():
    from flask_cors import CORS
    from flask_openapi3 import Info, OpenAPI
    from flask_socketio import SocketIO

    from app.config import Config
    from app.extensions import bcrypt, db, jwt
    from app.message_job import process_messages
    from app.sockets import register_socket_handlers

    def process_messages_background_task():
        logger.info("Background task started")
        while True:
            with app.app_context():
                process_messages(socketio)
            socketio.sleep(1)

    info = Info(title="Chat API", version="1.0.0")
    app = OpenAPI(__name__, info=info)
    CORS(app)
    socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")
    config = Config()
    app.config.from_object(config)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    media_root = os.path.join(project_root, app.config["MEDIA_FOLDER"])
    app.config["MEDIA_ROOT"] = media_root
    os.makedirs(media_root, exist_ok=True)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    from app.routes import bp as api_blueprint

    app.register_api(api_blueprint, url_prefix="/api")
    register_socket_handlers(socketio)

    with app.app_context():
        db.create_all()

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        logger.info("Starting background task in the main worker process")
        socketio.start_background_task(target=process_messages_background_task)

    return app, socketio
