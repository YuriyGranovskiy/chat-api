from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Message, Chat, db, DoesNotExistError
from app import services

bp = Blueprint('users', __name__)

@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    try:
        token = services.register_user(data['username'], data['password'])
        return jsonify(access_token=token), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 409 

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    token = services.login_user(data['username'], data['password'])
    if not token:
        return jsonify({'error': 'Invalid credentials'}), 401
    return jsonify(access_token=token), 200

@bp.route('/chats', methods=['POST'])
@jwt_required()
def create_chat():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    chat_id = services.create_user_chat(
        user_id=current_user_id,
        name=data['name'],
        initial_message=data['initial']
    )
    return jsonify({'message': 'Chat created successfully', 'chat_id': chat_id}), 201

@bp.route('/chats/<string:chat_id>/messages', methods=['POST'])
@jwt_required()
def send_message(chat_id):
    # current_user_id = get_jwt_identity() ...
    data = request.get_json()
    try:
        message_id = services.create_message(chat_id, data['message'], 'USER')
        return jsonify({'message': 'Message sent successfully', 'message_id': message_id}), 200
    except DoesNotExistError:
        return jsonify({'error': 'Chat not found'}), 404

@bp.route('/chats/<string:chat_id>/messages', methods=['GET'])
@jwt_required()
def get_messages_in_chat(chat_id):
    limit = request.args.get('limit', default=10, type=int)
    last_message_id = request.args.get('last_message_id')
    try:
        message_list = services.get_messages(chat_id, last_message_id, limit)
        return jsonify({'messages': message_list}), 200
    except DoesNotExistError:
        return jsonify({'error': 'Chat not found'}), 404

@bp.route('/chats', methods=['GET'])
@jwt_required()
def get_chats():
    current_user_id = get_jwt_identity()
    chats_list = services.get_user_chats(current_user_id)
    return jsonify({'chats': chats_list}), 200

@bp.route('/chats/<string:chat_id>', methods=['GET'])
@jwt_required()
def get_chat(chat_id):
    chat = Chat.query.get(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404

    messages = Message.query.filter_by(chat_id=chat_id).all()
    message_list = [{'id': m.id, 'user_id': chat.user_id, 'message': m.message} for m in messages]
    return jsonify({'id': chat.id, 'user_id': chat.user_id, 'name': chat.name, 'messages': message_list}), 200

@bp.route('/chats/<string:chat_id>', methods=['DELETE'])
@jwt_required()
def delete_chat(chat_id):
    current_user_id = get_jwt_identity()
    if not chat_id:
        return jsonify({'message': 'Chat ID is required'}), 400

    if not services.is_user_in_chat(current_user_id, chat_id):
        return jsonify({'message': 'User is not in the specified chat'}), 403

    try:
        services.delete_chat(chat_id)
        return jsonify({'message': 'Chat deleted successfully'}), 200
    except DoesNotExistError as e:
        return jsonify({'message': str(e)}), 404
        