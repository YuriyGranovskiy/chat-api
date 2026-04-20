from flask_openapi3 import APIBlueprint
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import services
from app.api_models import (
    AddPersonaBody,
    ChatPath,
    ChatsResponseBody,
    CreateChatBody,
    CreatedBody,
    CreateMessageBody,
    ErrorData,
    GetChatResponseBody,
    LocationBody,
    LocationPath,
    LocationsListResponse,
    LoginBody,
    MessagesQuery,
    MessagesResponseBody,
    PersonaBody,
    PersonaPath,
    PersonasListResponse,
    ProfileBody,
    ProfilePath,
    ProfilesListResponse,
    RegisterBody,
    TokenResponse,
    WorldBody,
    WorldPath,
    WorldsListResponse,
)
from app.models import (
    Chat,
    DoesNotExistError,
    Location,
    Message,
    MessageType,
    Persona,
    UserProfile,
    World,
)

bp = APIBlueprint("users", __name__)

@bp.post("/register", responses={201: TokenResponse})
def register(body: RegisterBody) -> TokenResponse:
    try:
        token = services.register_user(body.username, body.password)
        return {"access_token": token}, 201
    except ValueError as error:
        return {"error": str(error)}, 409

@bp.post("/login", responses={200: TokenResponse})
def login(body: LoginBody) -> TokenResponse:
    token = services.login_user(body.username, body.password)
    if not token:
        return {"error": "Invalid credentials"}, 401
    return {"access_token": token}, 200

@bp.post("/chats")
@jwt_required()
def create_chat(body: CreateChatBody):
    current_user_id = get_jwt_identity()
    
    chat_id = services.create_user_chat(
        user_id=current_user_id,
        name=body.name,
        world_id=body.world_id,
        profile_id=body.profile_id,
        persona_ids=body.persona_ids,
        location_ids=body.location_ids
    )
    
    if body.initial:
        services.create_message(chat_id, body.initial, MessageType.ASSISTANT)
        
    return CreatedBody(id=chat_id).model_dump(), 201

@bp.post("/chats/<chat_id>/personas")
@jwt_required()
def add_persona_to_existing_chat(path: ChatPath, body: AddPersonaBody):
    try:
        services.add_persona_to_chat(path.chat_id, body.persona_id)
        return "", 200
    except DoesNotExistError:
        return ErrorData(error='Not found').model_dump(), 404

@bp.post("/chats/<string:chat_id>/messages")
@jwt_required()
def send_message(path: ChatPath, body: CreateMessageBody):
    try:
        services.create_message(path.chat_id, body.message, MessageType.USER)
        return "", 200
    except DoesNotExistError:
        return ErrorData(error='Chat not found').model_dump(), 404

@bp.get("/chats/<string:chat_id>/messages")
@jwt_required()
def get_messages_in_chat(path: ChatPath, query: MessagesQuery):
    try:
        message_list = services.get_messages(path.chat_id, query.last_message_id, query.limit)
        return MessagesResponseBody(messages=message_list).model_dump(), 200
    except DoesNotExistError:
        return ErrorData(error='Chat not found').model_dump(), 404

@bp.get("/chats")
@jwt_required()
def get_chats():
    current_user_id = get_jwt_identity()
    chats_list = services.get_user_chats(current_user_id)
    return ChatsResponseBody(chats=chats_list).model_dump(), 200

@bp.get("/chats/<string:chat_id>")
@jwt_required()
def get_chat(path: ChatPath):
    chat = Chat.query.get(path.chat_id)
    if not chat:
        return ErrorData(error='Chat not found').model_dump(), 404

    messages = Message.query.filter_by(chat_id=path.chat_id).all()
    message_list = [
        {
            "id": message.id,
            "user_id": chat.user_id,
            "message": services.message_text_for_client(message),
            "assistant_meta": message.assistant_meta,
        }
        for message in messages
    ]
    return GetChatResponseBody(
        id=chat.id,
        name=chat.name,
        user_id=chat.user_id,
        messages=message_list,
    ).model_dump(), 200

@bp.delete("/chats/<string:chat_id>")
@jwt_required()
def delete_chat(path: ChatPath):
    current_user_id = get_jwt_identity()
    if not path.chat_id:
        return ErrorData(error='Chat ID is required').model_dump(), 400

    if not services.is_user_in_chat(current_user_id, path.chat_id):
        return ErrorData(error='User is not in the specified chat').model_dump(), 403

    try:
        services.delete_chat(path.chat_id)
        return "", 200
    except DoesNotExistError as error:
        return ErrorData(error=str(error)).model_dump(), 404
        

@bp.post("/worlds")
@jwt_required()
def create_world(body: WorldBody):
    world = services.create_entity(World, name=body.name, description=body.description)
    return CreatedBody(id=world.id).model_dump(), 201

@bp.put("/worlds/<string:world_id>")
@jwt_required()
def update_world(path: WorldPath, body: WorldBody):
    if not path.world_id:
        return ErrorData(error='World ID is required').model_dump(), 400
    services.update_entity(World, path.world_id, name=body.name, description=body.description)    
    return CreatedBody(id=path.world_id).model_dump(), 200


@bp.get("/worlds", responses={200: WorldsListResponse})
@jwt_required()
def get_worlds():
    entities = services.get_entities(World)
    resp = WorldsListResponse(worlds=entities)
    return resp.model_dump(), 200

@bp.delete("/worlds/<string:world_id>")
@jwt_required()
def delete_world(path: WorldPath):
    if not path.world_id:
        return ErrorData(error='World ID is required').model_dump(), 400
    try:
        services.delete_entity(World, path.world_id)
        return "", 200
    except DoesNotExistError:
        return ErrorData(error='World not found').model_dump(), 404

@bp.post("/locations")
@jwt_required()
def create_location(body: LocationBody):
    loc = services.create_entity(Location, name=body.name, description=body.description)
    return CreatedBody(id=loc.id).model_dump(), 201

@bp.put("/locations/<string:location_id>")
@jwt_required()
def update_location(path: LocationPath, body: LocationBody):
    if not path.location_id:
        return ErrorData(error='Location ID is required').model_dump(), 400
    services.update_entity(Location, path.location_id, name=body.name, description=body.description)
    return CreatedBody(id=path.location_id).model_dump(), 200


@bp.delete("/locations/<string:location_id>")
@jwt_required()
def delete_location(path: LocationPath):
    if not path.location_id:
        return ErrorData(error='Location ID is required').model_dump(), 400
    try:
        services.delete_entity(Location, path.location_id)
        return "", 200
    except DoesNotExistError:
        return ErrorData(error='Location not found').model_dump(), 404

@bp.post("/personas")
@jwt_required()
def create_persona(body: PersonaBody):
    p = services.create_entity(Persona, name=body.name, description=body.description)
    return CreatedBody(id=p.id).model_dump(), 201
    
@bp.put("/personas/<string:persona_id>")
@jwt_required()
def update_persona(path: PersonaPath, body: PersonaBody):
    if not path.persona_id:
        return ErrorData(error='Persona ID is required').model_dump(), 400
    services.update_entity(Persona, path.persona_id, name=body.name, description=body.description)    
    return CreatedBody(id=path.persona_id).model_dump(), 200


@bp.delete("/personas/<string:persona_id>")
@jwt_required()
def delete_persona(path: PersonaPath):
    if not path.persona_id:
        return ErrorData(error='Persona ID is required').model_dump(), 400
    try:
        services.delete_entity(Persona, path.persona_id)
        return "", 200
    except DoesNotExistError:
        return ErrorData(error='Persona not found').model_dump(), 404

@bp.get("/personas", responses={200: PersonasListResponse})
@jwt_required()
def get_personas():
    entities = services.get_entities(Persona)
    resp = PersonasListResponse(personas=entities)
    return resp.model_dump(), 200


@bp.get("/locations", responses={200: LocationsListResponse})
@jwt_required()
def get_locations():
    entities = services.get_entities(Location)
    resp = LocationsListResponse(locations=entities)
    return resp.model_dump(), 200

@bp.post("/profiles")
@jwt_required()
def create_profile(body: ProfileBody):
    p = services.create_entity(UserProfile, name=body.name, description=body.description)
    return CreatedBody(id=p.id).model_dump(), 201
    
@bp.put("/profiles/<string:profile_id>")
@jwt_required()
def update_profile(path: ProfilePath, body: ProfileBody):
    if not path.profile_id:
        return ErrorData(error='Profile ID is required').model_dump(), 400
    services.update_entity(UserProfile, path.profile_id, name=body.name, description=body.description)    
    return CreatedBody(id=path.profile_id).model_dump(), 200


@bp.get("/profiles", responses={200: ProfilesListResponse})
@jwt_required()
def get_profiles():
    entities = services.get_entities(UserProfile)
    resp = ProfilesListResponse(profiles=entities)
    return resp.model_dump(), 200


@bp.delete("/profiles/<string:profile_id>")
@jwt_required()
def delete_profile(path: ProfilePath):
    if not path.profile_id:
        return ErrorData(error='Profile ID is required').model_dump(), 400
    try:
        services.delete_entity(UserProfile, path.profile_id)
        return "", 200
    except DoesNotExistError:
        return ErrorData(error='Profile not found').model_dump(), 404