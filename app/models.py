import enum
import ulid

from app.extensions import bcrypt, db


def _new_ulid() -> str:
    return str(ulid.new())


def get_ulid() -> str:
    return _new_ulid()


chat_personas = db.Table(
    "chat_personas",
    db.Column("chat_id", db.String(28), db.ForeignKey("chat.id"), primary_key=True),
    db.Column("persona_id", db.String(28), db.ForeignKey("persona.id"), primary_key=True),
)

chat_locations = db.Table(
    "chat_locations",
    db.Column("chat_id", db.String(28), db.ForeignKey("chat.id"), primary_key=True),
    db.Column("location_id", db.String(28), db.ForeignKey("location.id"), primary_key=True),
)


class User(db.Model):
    id = db.Column(db.String(28), primary_key=True, default=get_ulid)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"User('{self.username}')"

class MessageType(enum.Enum):
    USER = 1
    ASSISTANT = 2
    SYSTEM = 3

class Status(enum.Enum):
    NEW = 1
    PROCESSING = 2
    PROCESSED = 3

class World(db.Model):
    id = db.Column(db.String(28), primary_key=True, default=get_ulid)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    image_path = db.Column(db.String(512), nullable=True)
    image_access_token = db.Column(db.String(64), nullable=True, unique=True)

    @property
    def image_url(self) -> str | None:
        if self.image_access_token:
            return f"/api/media/{self.image_access_token}"
        return None

class Chat(db.Model):
    id = db.Column(db.String(28), primary_key=True, default=_new_ulid)
    user_id = db.Column(db.String(28), db.ForeignKey("user.id"))
    name = db.Column(db.String(64), nullable=False)
    profile_id = db.Column(db.String(28), db.ForeignKey("user_profile.id"))
    personas = db.relationship("Persona", secondary=chat_personas, backref="chats")
    available_locations = db.relationship("Location", secondary=chat_locations)
    world_id = db.Column(db.String(28), db.ForeignKey("world.id"))
    scenario = db.Column(db.Text, nullable=True)
    messages = db.relationship("Message", backref="chat", lazy=True)

    def __repr__(self) -> str:
        return f"Chat('{self.user_id}', '{self.name}')"

class Message(db.Model):
    id = db.Column(db.String(28), primary_key=True)
    chat_id = db.Column(db.String(28), db.ForeignKey("chat.id", ondelete="RESTRICT"))
    sender_type = db.Column(db.Enum(MessageType))
    message = db.Column(db.String(1024), nullable=False)
    # JSON scene metadata (location, persons, clothing, ammunition, ...); NULL for user/system and legacy rows.
    # Existing DBs: ALTER TABLE message ADD COLUMN assistant_meta TEXT;
    assistant_meta = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(Status), default=Status.NEW, server_default=Status.NEW.name)


class UserProfile(db.Model):
    id = db.Column(db.String(28), primary_key=True, default=get_ulid)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    chats = db.relationship("Chat", backref="user_profile", lazy=True)

class Location(db.Model):
    id = db.Column(db.String(28), primary_key=True, default=get_ulid)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    image_path = db.Column(db.String(512), nullable=True)
    image_access_token = db.Column(db.String(64), nullable=True, unique=True)

    @property
    def image_url(self) -> str | None:
        if self.image_access_token:
            return f"/api/media/{self.image_access_token}"
        return None

class Persona(db.Model):
    id = db.Column(db.String(28), primary_key=True, default=get_ulid)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    image_path = db.Column(db.String(512), nullable=True)
    image_access_token = db.Column(db.String(64), nullable=True, unique=True)

    @property
    def image_url(self) -> str | None:
        if self.image_access_token:
            return f"/api/media/{self.image_access_token}"
        return None

class DoesNotExistError(Exception):
    pass
