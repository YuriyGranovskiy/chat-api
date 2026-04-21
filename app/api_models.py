from typing import Any

from flask_openapi3 import FileStorage
from pydantic import BaseModel, Field

class RegisterBody(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str

class LoginBody(BaseModel):
    username: str
    password: str

class WorldBody(BaseModel):
    name: str
    description: str

class PersonaBody(BaseModel):
    name: str
    description: str

class LocationBody(BaseModel):
    name: str
    description: str

class ProfileBody(BaseModel):
    name: str
    description: str

class CreatedBody(BaseModel):
    id: str

class ChatPath(BaseModel):
    chat_id: str

class WorldPath(BaseModel):
    world_id: str

class PersonaPath(BaseModel):
    persona_id: str

class LocationPath(BaseModel):
    location_id: str

class ProfilePath(BaseModel):
    profile_id: str


class MediaPath(BaseModel):
    token: str


class EntityImageUploadForm(BaseModel):
    file: FileStorage


class ErrorData(BaseModel):
    error: str

class CreateChatBody(BaseModel):
    name: str
    world_id: str | None = None
    profile_id: str
    persona_ids: list[str] = Field(default_factory=list)
    location_ids: list[str] = Field(default_factory=list)
    initial: str | None = None

class AddPersonaBody(BaseModel):
    persona_id: str

class CreateMessageBody(BaseModel):
    message: str

class MessagesResponseBody(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)

class ChatsResponseBody(BaseModel):
    chats: list[dict[str, Any]]

class GetChatResponseBody(BaseModel):
    id: str
    name: str
    user_id: str
    messages: list[dict[str, Any]]

class MessagesQuery(BaseModel):
    limit: int = 10
    last_message_id: str | None = None

class PersonaData(BaseModel):
    id: str
    name: str
    description: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}

class PersonasListResponse(BaseModel):
    personas: list[PersonaData]


class LocationData(BaseModel):
    id: str
    name: str
    description: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


class LocationsListResponse(BaseModel):
    locations: list[LocationData]


class WorldData(BaseModel):
    id: str
    name: str
    description: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


class WorldsListResponse(BaseModel):
    worlds: list[WorldData]


class ProfileData(BaseModel):
    id: str
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class ProfilesListResponse(BaseModel):
    profiles: list[ProfileData]
