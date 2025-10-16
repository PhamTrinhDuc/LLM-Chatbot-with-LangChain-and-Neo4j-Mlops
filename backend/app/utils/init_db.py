"""
Database initialization script
Creates all tables and optionally seeds with sample data
"""
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utils.database import create_tables, drop_tables, engine, Base
from sqlalchemy_utils import database_exists, create_database

print("Importing models...")
from models.users import User
from models.conversation import Conversation, Message

# Check and create database if it doesn't exist
def ensure_database():
    if not database_exists(engine.url):
        print("Database does not exist. Creating database...")
        create_database(engine.url)
        print("Database created successfully!")
    else:
        print("Database already exists.")

def init_database():
    """Initialize the database by creating all tables"""
    print(f"Tables to create: {list(Base.metadata.tables.keys())}")
    create_tables()
    print("Database tables created successfully!")

def reset_database():
    """Reset the database by dropping and recreating all tables"""
    print("Dropping existing tables...")
    drop_tables()
    print("Creating new tables...")
    create_tables()
    print("Database reset successfully!")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database management script")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--reset", action="store_true", help="Reset database")
    
    args = parser.parse_args()
    
    ensure_database()
    
    if args.reset:
        reset_database()
    elif args.init:
        init_database()
    else:
        print("Please specify --init or --reset")