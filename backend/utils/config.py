from dataclasses import dataclass
import os
from dotenv import load_dotenv
load_dotenv(".env.dev")

@dataclass
class AppConfig: 

  # LLM AND EMBEDDING MODEL CONFIGURATION
  OPENAI_LLM: str = "gpt-4o-mini"
  GOOGLE_LLM: str = "models/gemini-2.5-flash-lite"
  OPENAI_EMBEDDING: str="text-embedding-3-small"
  GOOGLE_EMBEDDING: str="models/gemini-embedding-001"
  HF_EMBEDDING_API: str = os.getenv("HF_EMBEDDING_API")
  OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
  GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")

  # DATABASE CONFIGURATION
  NEO4J_URI: str = os.getenv("NEO4J_URI")
  NEO4J_USER: str = os.getenv("NEO4J_USER")
  NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD")
  INDEX_NAME_NEO4J:str = "reviews"
  INDEX_NAME_ELS: str = "healthcare"
  REDIS_URL: str = os.getenv("REDIS_URL")
  DATABASE_URL: str = os.getenv("DATABASE_URL")

  # VECTOR STORE AND LLM PARAMETERS
  VECTOR_SIZE: int=1536
  TEMPERATURE: float=0
  REVIEW_TOP_K: int=10
  CYPHER_TOP_K: int=5
  MEMORY_TOP_K: int=5
  TTL: int=86400  # 24 hours in seconds
  LANGUAGE: str = "Vietnamese"

  # PROCESSING DATA FOR CHUNKING PDF 
  MIN_CHUNK_SIZE: int = 200
  MAX_CHUNK_SIZE: int = 1500
  TARGET_CHUNK_SIZE: int = 800
  CHUNK_OVERLAP: int = 200

  SECTION_PATTERN = r'^(\d+(?:\.\d+)*)\s+[A-ZÀ-Ỹ]' # → Match: "1.2.3 Tên section"
  
  CRITERIA_PATTERN = r'(?=\n[A-Z]\.\s)'  # → Match: "A. ", "B. ", "C. " 
  CRITERIA_LABEL_PATTERN = r'^([A-Z])\.\s'

  SUB_ITEM_PATTERN = r'(?=\n\d+\.\s)'
  SUB_ITEM_LABEL_PATTERN = r'^\d+\.\s'  # → Match: "1. ", "2. ", "3. "

  PAGE_FOOTER_PATTERN = r'\b[Cc]hỉ sử dụng tài liệu'  # → Bỏ qua footer trang 
  SPLIT_SENTENCE_PATTERN = r'(?<=[.!?])\s+'


  # PATH DATA
  DSM5_PATH: str = "/home/ducpham/workspace/LLM-Chatbot-with-LangChain-and-Neo4j/data/dsm-5-cac-tieu-chuan-chan-doan.pdf"

  DSM5_CHUNKS_PATH: str = "/home/ducpham/workspace/LLM-Chatbot-with-LangChain-and-Neo4j/data/dsm5_chunks.json"
  