# Message Compacting Implementation Plan

## Overview
The system will implement message compacting logic to ensure token usage stays within limits during chat processing. When 75% of available tokens are used, the system will automatically summarize previous messages using Ollama.

## Key Components

### Token Limit Check
1. **Token Calculation**: Create a helper function to calculate total tokens in the current conversation.
2. **Threshold Check**: Compare token count against 75% of the configured limit.
3. **Compact Decision**: If threshold is reached, trigger message compacting.

### Message Compacting Process
1. **Summarization Request**:
   - Send a request to Ollama with a special prompt instructing it to create a concise summary.
   - The summarization should preserve key context and references while reducing redundancy.

2. **Message Update**:
   - Mark original messages as "COMPACTED" or similar status.
   - Store the summarized message(s) in the database.

3. **Context Management**:
   - Ensure compacted history is used as starting point for future processing.
   - Maintain ability to retrieve full history if needed (flagged by user).

### Database Changes
1. Add a new `status` field for messages:
   - `COMPACTED`
   - `SUMMARY`

2. Add an optional `summary_id` field to link compacted messages with their summaries.

## Implementation Steps

### Step 1: Create Helper Functions
- **calculate_tokens()**: Counts tokens in messages using the existing tokenizer.
- **should_compact()**: Checks if token count exceeds threshold.
- **compact_conversation()**: Handles summarization and database updates.

### Step 2: Integrate into Message Processing Flow

```python
def process_messages(socketio_app):
    chats = Chat.query.filter_by(...).all()

    for chat in chats:
        messages = get_new_messages(chat.id)
        
        if should_compact(messages):
            compact_conversation(chat.id, socketio_app)

        # Process new message with Ollama
```

### Step 3: Database Schema Updates

```python
# Add to models.py
class Message(db.Model):
    # ... existing fields ...
    status = db.Enum(MessageType)  # Add status field
    summary_id = db.Column(db.String(28), nullable=True)  # Optional field for summaries
```

### Step 4: Implement Summarization Logic

```python
def compact_conversation(chat_id, socketio_app):
    # Get conversation history
    messages = Message.query.filter_by(chat_id=chat_id).order_by(Message.id).all()
    
    # Prepare context for summarization
    prompt = f"Summarize the following chat while preserving key references: {messages}"
    
    # Request summary from Ollama
    result = ollama.chat(model="mistral", messages=[{
        "role": "user",
        "content": prompt
    }])
    
    # Store compacted history and update original messages status
    for msg in messages:
        msg.status = MessageType.COMPACTED
        db.session.add(msg)
        
    # Create new summary message
    new_summary = Message(
        id=str(ulid()),
        chat_id=chat_id,
        sender_type=MessageType.SYSTEM,  # Or create a new type
        message=result["message"]["content"],
        status=Message.PROCESSED
    )
    
    db.session.add(new_summary)
    db.session.commit()
```

## Error Handling and Logging

1. **Logging**:
   - Add logging before and after each critical step.
   - Include token counts, compacting triggers, and summarization results.

2. **Error Handling**:
   - Catch exceptions during Ollama requests and database operations.
   - Rollback changes if compacting fails midway.

## Monitoring and Testing

1. **Monitoring**:
   - Log token usage metrics.
   - Track number of compactions performed.

2. **Testing**:
   - Test edge cases where messages are exactly at 75% limit.
   - Verify that compacted conversations still retain essential information.

## Final Notes

- This implementation maintains backward compatibility with existing chat functionality.
- The compacting process is designed to be transparent to end-users, though they will see summarized content.
- Performance optimizations may need to be applied if handling very large conversations frequently.

# Conclusion
The message compacting system ensures efficient token usage while maintaining a coherent conversation flow. By leveraging Ollama for summarization, the implementation keeps the system lightweight and consistent with existing architecture.