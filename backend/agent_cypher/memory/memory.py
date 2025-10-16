
import os
import sys
import json
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from datetime import datetime
from typing import Dict
from redis import Redis, ConnectionError
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain.memory import ConversationBufferMemory
from models.coversation_his import ConversationHistory
from dotenv import load_dotenv

load_dotenv(".env.dev")
REDIS_URL = os.getenv("REDIS_URL")


class MemoryPersistenceAgent: 
  def __init__(self, 
               user_id: str, 
               redis_url: str,
               db_url: str,
               session_id: str,
               ttl: int=84600):
    
    self.user_id = user_id
    self.redis_url = redis_url
    self.ttl = ttl
    self.session_id = session_id or f"session_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # PostgreSQL for permanent storage
    engine = create_engine(url=db_url)
    Base = declarative_base()
    Base.metadata.create_all(self.engine)
    Session = sessionmaker(bind=engine)
    self.db_session = Session()

    # Redis for fast access
    try:  
      self.redis_client = Redis.from_url(url=redis_url)
    except ConnectionError as e:
      print(f"Redis connection error: {e}")
    self.memory = self.get_memory()


  def get_memory(self): 
    self.message_history = RedisChatMessageHistory(session_id=self.session_id, 
                                                    url=self.redis_url, 
                                                    ttl=self.ttl) # 24hours
    memory = ConversationBufferMemory(
      chat_memory=self.message_history, 
      memory_key="chat_history", 
      return_messages=True, 
      output_key="output"
    )
    return memory
  
  def _save_to_db(self, message_type: str, content: str, metadata: Dict=None): 
    """Sync message to PostgreSQL"""
    conversation = ConversationHistory(
      session_id=self.session_id, 
      user_id=self.user_id, 
      message_type=message_type, 
      content=content, 
      metadata=json.dumps(metadata or {})
    )

    self.db_session.add(conversation)
    self.db_session.commit()
  
  def _load_from_db(self): 
    """Load conversation history DB to Redis memory"""
    if self.redis_client.ttl(name=self.session_id) == -1:
      messages = self.db_session.query(ConversationHistory).filter_by(
            session_id=self.session_id
        ).order_by(ConversationHistory.timestamp).all()
        
      for msg in messages:
        if msg.message_type == 'human':
            self.message_history.add_user_message(msg.content)
        elif msg.message_type == 'ai':
            self.message_history.add_ai_message(msg.content)
    

  def cleanup_old_sessions(self, days: int = 30):
    """Delete sessions older than X days"""
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    self.db_session.query(ConversationHistory).filter(
        ConversationHistory.timestamp < cutoff_date
    ).delete()
    self.db_session.commit()


if __name__ == "__main__": 
  memory_agent = MemoryPersistenceAgent(user_id=1)
  # memory_manager = memory_agent.memory

  # memory_manager.chat_memory.add_message(HumanMessage(content="Hello"))
  # memory_manager.chat_memory.add_message(AIMessage(content="Hi, how can I help?"))

  # print(memory_manager.load_memory_variables({}))
  
