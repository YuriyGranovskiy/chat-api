from flask import Blueprint, request, jsonify
from app.models import User, Message, db
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

@bp.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    message = data['message']

    user_id = '01JZGW44DYTJ3ZZBFH4B3XE7HN'
    new_message = Message(id=str(ulid()), user_id=user_id, message=message)
    db.session.add(new_message)
    db.session.commit()
    return jsonify({'message': 'Message sent successfully'}), 200

@bp.route('/get_messages', methods=['GET'])
def get_messages():
    messages = Message.query.all()
    message_list = [{'id': m.id, 'user_id': m.user_id, 'message': m.message} for m in messages]
    return jsonify({'messages': message_list}), 200

