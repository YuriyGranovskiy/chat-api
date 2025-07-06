from flask import Blueprint, request, jsonify
from app.models import User, Message, Chat, db
from ulid import ulid

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

    return jsonify({'message': 'User created successfully'}), 200

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    user = User.query.filter_by(username=username).first()
    if not user or user.password != password:
        return jsonify({'error': 'Invalid credentials'}), 401

    return jsonify({'message': 'User logged in successfully'}), 200

@bp.route('/chats', methods=['POST'])
def create_chat():
    data = request.get_json()
    user_id = data['user_id']
    name = data['name']
    new_chat = Chat(id=str(ulid()), user_id=user_id, name=name)
    db.session.add(new_chat)
    db.session.commit()
    return jsonify({'message': 'Chat created successfully'}), 200

@bp.route('/chats/<string:chatId>/messages', methods=['POST'])
def send_message(chatId):
    data = request.get_json()
    message = data['message']

    new_message = Message(id=str(ulid()), chat_id=chatId, message=message)
    db.session.add(new_message)
    db.session.commit()
    return jsonify({'message': 'Message sent successfully'}), 200

@bp.route('/chats/<string:chatId>/messages', methods=['GET'])
def get_messages(chatId):
    messages = Message.query.filter_by(chat_id=chatId).all()
    message_list = [{'id': m.id, 'chat_id': m.chat_id, 'message': m.message} for m in messages]
    return jsonify({'messages': message_list}), 200

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
    return jsonify({'id': chat.id, 'user_id': chat.user_id, 'name': chat.name}), 200
