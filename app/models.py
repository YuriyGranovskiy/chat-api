from app.extensions import db, bcrypt
from flask_sqlalchemy import SQLAlchemy
from ulid import ulid
import enum

class User(db.Model):
    id = db.Column(db.String(28), primary_key=True, default=lambda: str(ulid()))
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"User('{self.username}')"

class MessageType(enum.Enum):
    USER = 1
    ASSISTANT = 2
    SYSTEM = 3

class Status(enum.Enum):
    NEW = 1
    PROCESSING = 2
    PROCESSED = 3

class Chat(db.Model):
    id = db.Column(db.String(28), primary_key=True, default=lambda: str(ulid()))
    user_id = db.Column(db.String(28), db.ForeignKey('user.id'))
    name = db.Column(db.String(64), nullable=False)
    messages = db.relationship('Message', backref='chat', lazy=True)

    def __repr__(self):
        return f"Chat('{self.user_id}', '{self.name}')"

class Message(db.Model):
    id = db.Column(db.String(28), primary_key=True)
    chat_id = db.Column(db.String(28), db.ForeignKey('chat.id', ondelete='RESTRICT'))
    sender_type = db.Column(db.Enum(MessageType))
    message = db.Column(db.String(1024), nullable=False)
    status = db.Column(db.Enum(Status), default=Status.NEW, server_default=Status.NEW.name)

class DoesNotExistError(Exception):
    pass
