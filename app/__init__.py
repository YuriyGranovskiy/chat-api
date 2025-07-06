from flask import Flask, Blueprint
from flask_socketio import SocketIO
from app.config import Config
from app.routes import bp
from app.models import db

app = Flask(__name__)
socketio = SocketIO(app)
config = Config()
app.config.from_object(config)

print(__name__)

if __name__ == 'app':
    db.init_app(app)
    with app.app_context():
        db.create_all()
    app.register_blueprint(bp, url_prefix='/api')        
    app.run(debug=config.DEBUG)

