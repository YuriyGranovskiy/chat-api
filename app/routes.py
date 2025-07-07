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

@bp.route('/chats/<string:chat_id>/messages', methods=['POST'])
def send_message(chat_id):
    data = request.get_json()
    message = data['message']
    try:
        message_id = create_message(chat_id, message)    
        return jsonify({'message': 'Message sent successfully', 'message_id': message_id}), 200
    except DoesNotExistError:
        return jsonify({'error': 'Chat not found'}), 400

@bp.route('/chats/<string:chat_id>/messages', methods=['GET'])
def get_messages_in_chat(chat_id):
    limit = request.args.get('limit', default=10, type=int)
    last_message_id = request.args.get('last_message_id')

    try:
        message_list = get_messages(chat_id, last_message_id, limit)
        return jsonify({'messages': message_list}), 200
    except DoesNotExistError:
        return jsonify({'error': 'Chat not found'}), 400    

@bp.route('/chats', methods=['GET'])
def get_chats():
    user_id = request.args.get('user_id')
    chats = Chat.query.filter_by(user_id=user_id).all()
    chat_list = [{'id': c.id, 'user_id': c.user_id, 'name': c.name} for c in chats]
    return jsonify({'chats': chat_list}), 200

@bp.route('/chats/<string:chat_id>', methods=['GET'])
def get_chat(chat_id):
    chat = Chat.query.get(chat_id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404

    messages = Message.query.filter_by(chat_id=chat_id).all()
    message_list = [{'id': m.id, 'user_id': chat.user_id, 'message': m.message} for m in messages]
    return jsonify({'id': chat.id, 'user_id': chat.user_id, 'name': chat.name, 'messages': message_list}), 200
