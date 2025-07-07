from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
import enum

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.String(28), primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return f"User('{self.username}')"

class Chat(db.Model):
    id = db.Column(db.String(28), primary_key=True)
    user_id = db.Column(db.String(28), db.ForeignKey('user.id'))
    name = db.Column(db.String(64), nullable=False)  # добавлено поле name
    messages = db.relationship('Message', backref='chat', lazy=True)

    def __repr__(self):
        return f"Chat('{self.user_id}', '{self.name}')"

class SendMessageType(enum.Enum):
    USER = 1
    AGENT = 2

class Message(db.Model):
    id = db.Column(db.String(28), primary_key=True)
    chat_id = db.Column(db.String(28), db.ForeignKey('chat.id', ondelete='RESTRICT'))
    sender_type = db.Column(db.Enum(SendMessageType))
    message = db.Column(db.String(1024), nullable=False)

class DoesNotExistError(Exception):
    pass

