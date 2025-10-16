import os
from fastapi import FastAPI
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from utils.database import get_db, create_tables
from models import User

app = FastAPI()

app = FastAPI(
  title=os.getenv("APP_NAME", "LLM Healcare Chatbot Langchain"),
  version=os.getenv("APP_VERSION", "1.0.0"),
  description="LLM Healcare Chatbot Langchain"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", os.getenv('FRONTEND_URL')).split(","),
    allow_credentials=True,
    allow_methods=os.getenv("ALLOWED_METHODS", "GET,POST,PUT,DELETE").split(","),
    allow_headers=os.getenv("ALLOWED_HEADERS", "*").split(","),
)


@app.on_event("startup")
async def startup_event():
    """Create database tables on startup"""
    create_tables()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Healcare chatbot API",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/customers")
async def get_customers(db: Session = Depends(get_db)):
    customers = db.query(User).all()
    return customers

# uvicorn main:app --host 0.0.0.0 --port 8000 --reload