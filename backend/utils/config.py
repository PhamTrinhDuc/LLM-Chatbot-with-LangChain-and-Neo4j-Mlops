from dataclasses import dataclass
import os
from dotenv import load_dotenv
load_dotenv(".env.dev")

@dataclass
class AppConfig: 

  OPENAI_LLM: str = "gpt-4o-mini"
  GOOGLE_LLM: str = "models/gemini-2.5-flash-lite"

  OPENAI_EMBEDDING: str="text-embedding-3-small"
  GOOGLE_EMBEDDING: str="models/gemini-embedding-001"

  HF_EMBEDDING_API: str = os.getenv("HF_EMBEDDING_API")
  OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
  GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")

  NEO4J_URI: str = os.getenv("NEO4J_URI")
  NEO4J_USER: str = os.getenv("NEO4J_USER")
  NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD")
  INDEX_NAME:str = "reviews"

  REDIS_URL: str = os.getenv("REDIS_URL")
  DATABASE_URL: str = os.getenv("DATABASE_URL")
  
  INDEX_NAME: str = "healthcare"
  VECTOR_SIZE: int=1536
  TEMPERATURE: float=0
  REVIEW_TOP_K: int=10
  CYPHER_TOP_K: int=5
  MEMORY_TOP_K: int=5
  TTL: int=86400  # 24 hours in seconds
  LANGUAGE: str = "Vietnamese"