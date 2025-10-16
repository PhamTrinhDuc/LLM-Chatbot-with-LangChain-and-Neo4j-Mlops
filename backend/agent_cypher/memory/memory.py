
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from datetime import datetime
from redis import Redis, ConnectionError
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain.memory import ConversationBufferMemory
from models.coversation_his import Conversation, Message

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
    self.engine = create_engine(url=db_url)
    Base = declarative_base()
    Base.metadata.create_all(self.engine)
    Session = sessionmaker(bind=self.engine)
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
  
  def _save_to_db(self, message_type: str, content: str, title: str = None):
    """Sync message to PostgreSQL using Conversation and Message models"""
    # Tìm hoặc tạo Conversation
    conversation = self.db_session.query(Conversation).filter_by(session_id=self.session_id).first()
    if not conversation:
        conversation = Conversation(
            user_id=self.user_id,
            session_id=self.session_id,
            title=title,
            is_active=True
        )
        self.db_session.add(conversation)
        self.db_session.commit()  # Để lấy conversation.id

    # Tạo Message mới
    message = Message(
        conversation_id=conversation.id,
        message_type=message_type,
        content=content
    )
    self.db_session.add(message)
    self.db_session.commit()
  
  def _load_from_db(self): 
    """Load conversation history from DB to Redis memory"""
    # Kiểm tra nếu Redis key không có TTL (tức là chưa load từ DB)
    if self.redis_client.ttl(name=self.session_id) == -1:
      # Tìm conversation theo session_id
      conversation = self.db_session.query(Conversation).filter_by(
          session_id=self.session_id
      ).first()
      
      if conversation:
        # Lấy tất cả messages của conversation này, sắp xếp theo thời gian
        messages = self.db_session.query(Message).filter_by(
            conversation_id=conversation.id
        ).order_by(Message.created_at).all()
        
        # Load messages vào Redis memory
        for msg in messages:
          if msg.message_type == 'human':
              self.message_history.add_user_message(msg.content)
          elif msg.message_type == 'ai':
              self.message_history.add_ai_message(msg.content)

  def cleanup_old_sessions(self, days: int = 30):
    """Delete sessions older than X days"""
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Xóa các conversations cũ hơn X ngày
    old_conversations = self.db_session.query(Conversation).filter(
        Conversation.created_at < cutoff_date
    ).all()
    
    # Xóa messages trước (do foreign key constraint)
    for conversation in old_conversations:
      self.db_session.query(Message).filter_by(
          conversation_id=conversation.id
      ).delete()
    
    # Sau đó xóa conversations
    self.db_session.query(Conversation).filter(
        Conversation.created_at < cutoff_date
    ).delete()
    
    self.db_session.commit()
    print(f"Cleaned up {len(old_conversations)} old conversations older than {days} days")


if __name__ == "__main__": 
  from dotenv import load_dotenv

  load_dotenv('.env.dev')

  memory_agent = MemoryPersistenceAgent(user_id=1, session_id="session_user_1", 
                                        redis_url=os.getenv("REDIS_URL"), 
                                        db_url=os.getenv("DATABASE_URL"))
  print(memory_agent.get_memory().load_memory_variables({}))
  
