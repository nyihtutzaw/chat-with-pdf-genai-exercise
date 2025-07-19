"""In-memory conversation state management."""
from typing import Dict, List, Optional
import uuid
from datetime import datetime, timezone

class Message:
    """Represents a single message in the conversation."""
    
    def __init__(self, role: str, content: str):
        self.id = str(uuid.uuid4())
        self.role = role  # 'user' or 'assistant'
        self.content = content
        self.timestamp = datetime.now(timezone.utc)
        self.metadata: Dict = {}
        
    def to_dict(self) -> Dict:
        """Convert message to dictionary format."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

class Conversation:
    """Manages a single conversation session."""
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.messages: List[Message] = []
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self.metadata: Dict = {}
      
        self.context = {
            'last_intent': None,
            'last_entities': {},
            'conversation_topics': []
        }
    
    def add_message(self, role: str, content: str, **metadata) -> Message:
        """Add a new message to the conversation."""
        message = Message(role, content)
        message.metadata.update(metadata)
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)
        return message
    
    def get_messages(self, limit: Optional[int] = None) -> List[Dict]:
        """Get conversation messages, optionally limited in number."""
        messages = self.messages
        if limit and limit > 0:
            messages = messages[-limit:]
        return [msg.to_dict() for msg in messages]
        
    
        
    def update_context(self, intent: Optional[str] = None, 
                      entities: Optional[Dict] = None,
                      topics: Optional[List[str]] = None) -> None:
        """Update the conversation context."""
        if intent:
            self.context['last_intent'] = intent
        if entities:
            self.context['last_entities'].update(entities)
        if topics:
            self.context['conversation_topics'].extend(
                t for t in topics if t not in self.context['conversation_topics']
            )
        self.updated_at = datetime.utcnow()
        
    def get_context(self) -> Dict:
        """Get the current conversation context."""
        return self.context.copy()
    
    def clear(self) -> None:
        """Clear all messages from the conversation."""
        self.messages = []
        self.updated_at = datetime.utcnow()

class ConversationManager:
    """Manages multiple conversation sessions in memory."""
    
    def __init__(self):
        self.sessions: Dict[str, Conversation] = {}
    
    def get_conversation(self, session_id: Optional[str] = None) -> 'Conversation':
        """Get an existing conversation or create a new one."""
        if not session_id or session_id not in self.sessions:
            return self.create_conversation(session_id)
        return self.sessions[session_id]
    
    def create_conversation(self, session_id: Optional[str] = None) -> 'Conversation':
        """Create a new conversation."""
        if session_id and session_id in self.sessions:
            raise ValueError(f"Session {session_id} already exists")
            
        conversation = Conversation(session_id)
        self.sessions[conversation.session_id] = conversation
        return conversation
    
    def clear_conversation(self, session_id: str) -> bool:
        """Clear a specific conversation."""
        if session_id in self.sessions:
            self.sessions[session_id].clear()
            return True
        return False
    
    def end_conversation(self, session_id: str) -> bool:
        """End and remove a conversation."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

# Global instance for the application
conversation_manager = ConversationManager()
