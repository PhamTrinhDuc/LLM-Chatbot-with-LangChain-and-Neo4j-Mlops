import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from agents.hospital_rag_agent import HospitalRAGAgent
from tools.health_tool import DSM5RetrievalTool
from tools import CypherTool
from utils import AppConfig, logger
from utils.logging import trace_id_ctx
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json
import uuid

from app.database import get_db, User, Conversation, Message, init_db
from app.schemas import (
  UserRegister, 
  QueryRequest, 
  UserLogin, 
  ConversationCreate,
  MessageCreate
)
from mlops import setup_metrics, setup_tracing, monitor_endpoint


def _setup_middlewares(app: FastAPI) -> None:
    """Setup all middlewares for the app."""
    
    # Trace ID middleware - must be first to ensure all logs have trace_id
    @app.middleware("http")
    async def add_trace_id_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        trace_id_ctx.set(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def _setup_monitoring(app: FastAPI) -> None:
    """Setup monitoring tools (tracing, metrics)."""
    setup_tracing(
        app=app,
        service_name=AppConfig.APP_NAME,
        jaeger_endpoint=AppConfig.JAEGER_ENDPOINT
    )
    setup_metrics(app=app)


def _create_agent(user_id: str) -> HospitalRAGAgent:
    """Create a fresh agent instance (stateless approach)."""
    return HospitalRAGAgent(
        llm_model="openai",
        embedding_model="openai",
        user_id=user_id,
        type_memory="redis"
    )


def _initialize_tools() -> tuple:
    """Initialize all tools and agents."""
    # These are stateless and can be shared
    dsm5_tool = DSM5RetrievalTool(embedding_model="google", top_k=10)
    cypher_tool = CypherTool(llm_model="google")
    return dsm5_tool, cypher_tool


def create_app() -> FastAPI:
    """Application factory: creates and configures the FastAPI app."""
    app = FastAPI(
        title="DSM-5 & Hospital Chatbot",
        description="RAG chatbot with hospital and DSM-5 data",
    )
    _setup_monitoring(app)
    _setup_middlewares(app)
    
    return app


app = create_app()
# Initialize tools (lazy initialization can be done in startup event if needed)
dsm5_tool, cypher_tool = _initialize_tools()

@app.on_event("shutdown")
def shutdown():
    logger.info("Graceful shutdown started")
    logger.complete()


@app.get("/health")
async def get_status():
    logger.info("Health check requested")
    return {"status": "running", "service": "Hospital & DSM-5 Chatbot"}

# ============================================================
# Agent chat
# ============================================================

@app.post("/chat")
@monitor_endpoint("chat")
async def chat(request: QueryRequest):
  """
  Chat endpoint - returns full response.
  """
  try:
    logger.info(f"Starting chat for user {request.user_id}, query: {request.query}")
    agent = _create_agent(request.user_id)
    result = await agent.ainvoke(query=request.query)
    return {
        "query": request.query,
        "answer": result.get("output"),
        "steps": len(result.get("intermediate_steps", []))
    }
  except Exception as e:
    logger.error(f"Chat error: {str(e)}")
    raise HTTPException(status_code=500, detail=str(e))


@app.post("/stream")
@monitor_endpoint("stream")
async def stream_chat(request: QueryRequest):
  """
  Streaming endpoint - returns results as they come.
  """
  logger.info(f"Starting streaming chat for user {request.user_id}, query: {request.query}")
  async def event_generator():
    try:
      agent = _create_agent(request.user_id)
      async for chunk in agent.astream(query=request.query):
          if 'actions' in chunk:
              for action in chunk['actions']:
                  yield f"data: {json.dumps({'type': 'tool', 'tool': action.tool, 'input': str(action.tool_input)})}\n\n"
          elif 'steps' in chunk:
              for step in chunk['steps']:
                  yield f"data: {json.dumps({'type': 'result', 'result': str(step.observation)[:200]})}\n\n"
          elif 'output' in chunk:
              yield f"data: {json.dumps({'type': 'answer', 'answer': chunk['output']})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
  
  return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============================================================
# DSM-5 Endpoints
# ============================================================

@app.post("/dsm5/search")
async def dsm5_search(request: QueryRequest):
    """Search DSM-5 diagnostic criteria."""
    try:
        response = await dsm5_tool._arun(query=request.query)
        return {
            "query": request.query,
            "response": response,
            "results": response.count("Section")
        }
    except Exception as e:
        logger.error(f"DSM5 search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dsm5/hybrid")
async def dsm5_hybrid_search(request: QueryRequest):
    """Hybrid search (keyword + semantic) for DSM-5."""
    try:
        results = dsm5_tool.retriever.hybrid_search(
            query=request.query,
            top_k=request.top_k,
            keyword_weight=0.6,
            vector_weight=1.2,
            include_context=False
        )
        formatted = dsm5_tool._format_results(results, include_scores=False)
        return {
            "query": request.query,
            "response": formatted,
            "results_count": len(results)
        }
    except Exception as e:
        logger.error(f"DSM5 hybrid search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dsm5/criteria")
async def dsm5_criteria_search(disorder: str, criteria: str = None):
    """Search DSM-5 by disorder name and criterion."""
    try:
        results = dsm5_tool.retriever.search_by_criteria(
            disorder_name=disorder,
            criteria=criteria
        )
        formatted = dsm5_tool._format_results(results, include_scores=False)
        return {
            "disorder": disorder,
            "criteria": criteria,
            "response": formatted,
            "results_count": len(results)
        }
    except Exception as e:
        logger.error(f"DSM5 criteria search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Neo4j Cypher Endpoints
# ============================================================

@app.post("/cypher/query")
async def cypher_query(request: QueryRequest):
    """Query hospital data using Neo4j Cypher."""
    try:
        answer, generated_cypher = cypher_tool.cypher_chain.invoke(query=request.query)
        return {
            "query": request.query,
            "answer": answer,
            "cypher": generated_cypher
        }
    except Exception as e:
        logger.error(f"Cypher query error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cypher/patients")
async def cypher_patients(request: QueryRequest):
  """Search for patients."""
  try:
      answer, generated_cypher = cypher_tool.cypher_chain.invoke(
        query=f"Patient search: {request.query}"
      )
      return {
        "query": request.query,
        "answer": answer,
        "cypher": generated_cypher
      }
  except Exception as e:
      logger.error(f"Patient search error: {str(e)}")
      raise HTTPException(status_code=500, detail=str(e))


@app.post("/cypher/hospital-stats")
async def cypher_hospital_stats(request: QueryRequest):
    """Get hospital statistics."""
    try:
        answer, generated_cypher = cypher_tool.cypher_chain.invoke(
            query=f"Hospital statistics: {request.query}"
        )
        return {
            "query": request.query,
            "answer": answer,
            "cypher": generated_cypher
        }
    except Exception as e:
        logger.error(f"Hospital stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Authentication Endpoints
# ============================================================

@app.post("/auth/register")
async def register(user: UserRegister, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if user exists
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Create new user
    new_user = User(
        username=user.username,
        password_hash=User.hash_password(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "message": "User registered successfully",
        "user_id": new_user.id,
        "username": new_user.username
    }


@app.post("/auth/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    """Login user."""
    db_user = db.query(User).filter(User.username == user.username).first()
    
    if not db_user or not db_user.verify_password(user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    return {
        "message": "Login successful",
        "user_id": db_user.id,
        "username": db_user.username
    }


@app.get("/auth/users")
async def get_users(db: Session = Depends(get_db)):
    """Get all users (for debugging)."""
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username} for u in users]


# ============================================================
# Conversation Endpoints
# ============================================================

@app.get("/conversations/{username}")
async def get_conversations(username: str, db: Session = Depends(get_db)):
    """Get all conversations for a user."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user.id
    ).order_by(Conversation.updated_at.desc()).all()
    
    result = []
    for conv in conversations:
        msg_count = db.query(Message).filter(Message.conversation_id == conv.id).count()
        result.append({
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "message_count": msg_count
        })
    
    return result


@app.post("/conversations/{username}")
async def create_conversation(
    username: str, 
    conv: ConversationCreate,
    db: Session = Depends(get_db)
):
    """Create a new conversation."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_conv = Conversation(user_id=user.id, title=conv.title)
    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)
    
    return {
        "id": new_conv.id,
        "title": new_conv.title,
        "created_at": new_conv.created_at.isoformat()
    }


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Delete a conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conv)
    db.commit()
    
    return {"message": "Conversation deleted"}


@app.put("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: int,
    title: str,
    db: Session = Depends(get_db)
):
    """Update conversation title."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conv.title = title
    db.commit()
    
    return {"message": "Title updated", "title": title}


# ============================================================
# Message Endpoints
# ============================================================

@app.get("/messages/{conversation_id}")
async def get_messages(conversation_id: int, db: Session = Depends(get_db)):
    """Get all messages in a conversation."""
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()
    
    return [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat()
        }
        for msg in messages
    ]


@app.post("/messages/{conversation_id}")
async def add_message(
    conversation_id: int,
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """Add a message to a conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    new_msg = Message(
        conversation_id=conversation_id,
        role=message.role,
        content=message.content
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    
    return {
        "id": new_msg.id,
        "role": new_msg.role,
        "content": new_msg.content,
        "created_at": new_msg.created_at.isoformat()
    }


@app.delete("/messages/{conversation_id}")
async def clear_messages(conversation_id: int, db: Session = Depends(get_db)):
    """Clear all messages in a conversation."""
    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.commit()
    
    return {"message": "Messages cleared"}


# Run: uvicorn main:app --host 0.0.0.0 --port 8000 --reload