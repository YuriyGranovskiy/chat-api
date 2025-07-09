from app.models import Message
from sqlalchemy import desc

import ollama
    

def process_messages():
    message = Message.query.order_by(desc(Message.id)).limit(1).all()[0]
    result = ollama.generate(model='mistral', prompt=message.message)
    print(result['response'])
    
