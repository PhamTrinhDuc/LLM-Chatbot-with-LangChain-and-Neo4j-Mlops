"""
Database configuration and setup for the recommendation platform
"""
import os
from dotenv import load_dotenv

load_dotenv('.env.dev')

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables in the database"""
    print("Available tables to create:", Base.metadata.tables.keys())
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables in the database"""
    Base.metadata.drop_all(bind=engine)