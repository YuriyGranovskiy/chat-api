from app.logging_config import get_logging_config
from app.models import Message, Status, db, MessageType, Chat
from sqlalchemy import asc
from ulid import ulid
import ollama
import json
import logging.config

logging_config = logging.config.dictConfig(get_logging_config())
logger = logging.getLogger(__name__)

def process_messages():
    chats_with_new_user_messages = Chat.query.join(Message, Message.chat_id == Chat.id).filter_by(sender_type=MessageType.USER, status=Status.NEW).distinct().all()

    for chat in chats_with_new_user_messages:
        new_messages = Message.query.filter_by(chat_id=chat.id).order_by(asc(Message.id)).all()
        messages = []
        for message in new_messages:
            if message.sender_type == MessageType.SYSTEM:
                role = 'system'
            elif message.sender_type == MessageType.ASSISTANT:
                role = 'assistant'
            else:
                role = 'user'

            messages.append({
                "role": role,
                "content": message.message
            })

        try:
            result = ollama.chat(model="mistral", messages=messages)
            processed_message_id = str(ulid())
            new_processed_message = Message(id=processed_message_id, chat_id=message.chat_id, sender_type='ASSISTANT', message=result['message']['content'], status=Status.PROCESSED)
            db.session.add(new_processed_message)
            message.status = Status.PROCESSED
            db.session.commit()
            logger.info(f'Сообщение {message.id} успешно обработано и добавлено в базу')
        except Exception as e:
            logger.error(f'Ошибка при обработке сообщения {message.id}: {str(e)}')
