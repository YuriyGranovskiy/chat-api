from flask import Blueprint, request, jsonify
from app.models import User, Message, Chat, db, DoesNotExistError
from ulid import ulid
from app.services import create_message, get_messages

bp = Blueprint('users', __name__)

@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data['username']
    password = data['password']

    user_id = str(ulid())
    new_user = User(id=user_id, username=username, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User created successfully', 'user_id': user_id}), 200

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    user = User.query.filter_by(username=username).first()
    if not user or user.password != password:
        return jsonify({'error': 'Invalid credentials'}), 401

    return jsonify({'message': 'User logged in successfully', 'user_id': user.id}), 200

@bp.route('/chats', methods=['POST'])
def create_chat():
    data = request.get_json()
    user_id = data['user_id']
    name = data['name']
    new_chat = Chat(id=str(ulid()), user_id=user_id, name=name)
    db.session.add(new_chat)
    db.session.commit()

    return jsonify({'message': 'Chat created successfully', 'chat_id': new_chat.id}), 200

@bp.route('/chats/<string:chatId>/messages', methods=['POST'])
def send_message(chatId):
    data = request.get_json()
    message = data['message']
    try:
        message_id = create_message(chatId, message)    
        return jsonify({'message': 'Message sent successfully', 'message_id': message_id}), 200
    except DoesNotExistError:
        return jsonify({'error': 'Chat not found'}), 400

@bp.route('/chats/<string:chatId>/messages', methods=['GET'])
def get_messages_in_chat(chatId):
    limit = request.args.get('limit', default=10, type=int)
    lastMessageId = request.args.get('lastMessageId')

    try:
        message_list = get_messages(chatId, lastMessageId, limit)
        return jsonify({'messages': message_list}), 200
    except DoesNotExistError:
        return jsonify({'error': 'Chat not found'}), 400    

@bp.route('/chats', methods=['GET'])
def get_chats():
    user_id = request.args.get('user_id')
    chats = Chat.query.filter_by(user_id=user_id).all()
    chat_list = [{'id': c.id, 'user_id': c.user_id, 'name': c.name} for c in chats]
    return jsonify({'chats': chat_list}), 200

@bp.route('/chats/<string:chatId>', methods=['GET'])
def get_chat(chatId):
    chat = Chat.query.get(chatId)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404

    messages = Message.query.filter_by(chat_id=chatId).all()
    message_list = [{'id': m.id, 'user_id': chat.user_id, 'message': m.message} for m in messages]
    return jsonify({'id': chat.id, 'user_id': chat.user_id, 'name': chat.name, 'messages': message_list}), 200
