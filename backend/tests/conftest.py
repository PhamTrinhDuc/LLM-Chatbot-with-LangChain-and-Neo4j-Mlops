"""Pytest configuration and shared fixtures."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, Conversation, Message, User, get_db
from main import app

# Test database setup
TEST_DB_PATH = Path(__file__).parent / "test_chatbot.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def get_test_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db_session():
    """Setup test database schema once per session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    # Cleanup test database file after all tests
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(scope="function")
def setup_db():
    """Clear tables before each test."""
    # Clear all data
    session = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()

    yield

    # Clear all data after test
    session = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()


@pytest.fixture(scope="function")
def db(setup_db):
    """Get test database session."""
    return TestingSessionLocal()


@pytest.fixture(scope="function")
def client(setup_db):
    """Create test client with overridden database."""
    app.dependency_overrides[get_db] = get_test_db

    # Pass app only as positional argument (don't use app= keyword)
    test_client = TestClient(app)
    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session):
    """Create a test user."""
    user = User(username="testuser", password_hash=User.hash_password("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_user_2(db: Session):
    """Create a second test user."""
    user = User(username="testuser2", password_hash=User.hash_password("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_conversation(db: Session, test_user: User):
    """Create a test conversation."""
    conv = Conversation(user_id=test_user.id, title="Test Conversation")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@pytest.fixture
def test_messages(db: Session, test_conversation: Conversation):
    """Create test messages."""
    messages = [
        Message(
            conversation_id=test_conversation.id,
            role="user",
            content="Hello, how are you?",
        ),
        Message(
            conversation_id=test_conversation.id,
            role="assistant",
            content="I'm doing well, thank you!",
        ),
    ]
    db.add_all(messages)
    db.commit()
    for msg in messages:
        db.refresh(msg)
    return messages


@pytest.fixture
def mock_query_request():
    """Mock query request payload."""
    return {"query": "What is depression?", "user_id": "default", "session_id": None}


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "auth: mark test as authentication test")
    config.addinivalue_line("markers", "conversation: mark test as conversation test")
    config.addinivalue_line("markers", "message: mark test as message test")
    config.addinivalue_line("markers", "dsm5: mark test as DSM-5 tool test")
    config.addinivalue_line("markers", "cypher: mark test as Cypher query test")
