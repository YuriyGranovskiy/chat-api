from app.models import Message, Status, db
import ollama
from ulid import ulid

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
        except Exception as e:
            print(f"Error processing message {message.id}: {str(e)}")
