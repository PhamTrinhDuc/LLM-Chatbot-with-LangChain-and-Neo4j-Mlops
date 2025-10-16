from sqlalchemy import Column, String, DateTime, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json

Base = declarative_base()

# Database Model
class ConversationHistory(Base):
    __tablename__ = 'conversation_history'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), index=True)
    user_id = Column(String(255), index=True)
    message_type = Column(String(50))  # 'human' or 'ai'
    content = Column(Text)
    metadata = Column(Text)  # JSON string
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
      return {
        'id': self.id,
        'session_id': self.session_id,
        'user_id': self.user_id,
        'message_type': self.message_type,
        'content': self.content,
        'metadata': json.loads(self.metadata) if self.metadata else {},
        'timestamp': self.timestamp.isoformat()
      }
