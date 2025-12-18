from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    user_id: str = "default"
    session_id: str = None


# Auth models
class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class MessageCreate(BaseModel):
    role: str
    content: str


class ConversationCreate(BaseModel):
    title: str = "New Conversation"


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    
    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    
    class Config:
        from_attributes = True

