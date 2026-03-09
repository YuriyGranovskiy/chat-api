from typing import Any, List, Optional

from pydantic import BaseModel

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

class ErrorData(BaseModel):
    error: str

class CreateChatBody(BaseModel):
    name: str
    world_id: Optional[str] = None
    profile_id: str
    persona_ids: List[str] = []
    location_ids: List[str] = []
    initial: Optional[str] = None

class AddPersonaBody(BaseModel):
    persona_id: str

class CreateMessageBody(BaseModel):
    message: str

class MessagesResponseBody(BaseModel):
    messages: List[dict[str, Any]] = []

class ChatsResponseBody(BaseModel):
    chats: List[dict[str, Any]]

class GetChatResponseBody(BaseModel):
    id: str
    name: str
    user_id: str
    messages: List[dict[str, Any]]

class MessagesQuery(BaseModel):
    limit: int = 10
    last_message_id: Optional[str] = None

class PersonaData(BaseModel):
    id: str
    name: str
    description: str

    model_config = {"from_attributes": True}

class PersonasListResponse(BaseModel):
    personas: list[PersonaData]


class LocationData(BaseModel):
    id: str
    name: str
    description: str

    model_config = {"from_attributes": True}


class LocationsListResponse(BaseModel):
    locations: list[LocationData]


class WorldData(BaseModel):
    id: str
    name: str
    description: str

    model_config = {"from_attributes": True}


class WorldsListResponse(BaseModel):
    worlds: list[WorldData]


class ProfileData(BaseModel):
    id: str
    name: str
    description: str

    model_config = {"from_attributes": True}


class ProfilesListResponse(BaseModel):
    profiles: list[ProfileData]
