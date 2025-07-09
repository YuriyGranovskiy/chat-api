from app.logging_config import get_logging_config
from app.models import Message, Status, db
import ollama
from ulid import ulid
import logging.config

logging_config = logging.config.dictConfig(get_logging_config())
logger = logging.getLogger(__name__)

def process_messages():
    new_messages = Message.query.filter_by(status=Status.NEW).all()
    for message in new_messages:
        try:
            result = ollama.generate(model='mistral', prompt=message.message)
            processed_message_id = str(ulid())
            new_processed_message = Message(id=processed_message_id, chat_id=message.chat_id, sender_type='AGENT', message=result['response'], status=Status.PROCESSED)
            db.session.add(new_processed_message)
            message.status = Status.PROCESSED
            db.session.commit()
            logger.info(f'Сообщение {message.id} успешно обработано и добавлено в базу')
        except Exception as e:
            logger.error(f'Ошибка при обработке сообщения {message.id}: {str(e)}')
