"""Tests for message endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.message
def test_add_message(client: TestClient, test_conversation):
    """Test adding a message to conversation."""
    response = client.post(
        f"/messages/{test_conversation.id}",
        json={"role": "user", "content": "Hello!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "user"
    assert data["content"] == "Hello!"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.message
def test_add_assistant_message(client: TestClient, test_conversation):
    """Test adding assistant message."""
    response = client.post(
        f"/messages/{test_conversation.id}",
        json={"role": "assistant", "content": "I'm here to help!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"


@pytest.mark.message
def test_add_message_to_nonexistent_conversation(client: TestClient):
    """Test adding message to nonexistent conversation fails."""
    response = client.post(
        "/messages/9999",
        json={"role": "user", "content": "Test"}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.message
def test_get_messages(client: TestClient, test_messages):
    """Test retrieving messages from conversation."""
    conversation_id = test_messages[0].conversation_id
    response = client.get(f"/messages/{conversation_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["content"] == "Hello, how are you?"
    assert data[1]["content"] == "I'm doing well, thank you!"


@pytest.mark.message
def test_get_messages_empty_conversation(client: TestClient, test_conversation):
    """Test retrieving messages from empty conversation."""
    response = client.get(f"/messages/{test_conversation.id}")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.message
def test_get_messages_nonexistent_conversation(client: TestClient):
    """Test getting messages from nonexistent conversation."""
    response = client.get("/messages/9999")
    assert response.status_code == 200
    # Should return empty list
    data = response.json()
    assert data == []


@pytest.mark.message
def test_clear_messages(client: TestClient, test_messages):
    """Test clearing all messages in conversation."""
    conversation_id = test_messages[0].conversation_id
    
    # Verify messages exist
    response = client.get(f"/messages/{conversation_id}")
    assert len(response.json()) == 2
    
    # Clear messages
    response = client.delete(f"/messages/{conversation_id}")
    assert response.status_code == 200
    assert "cleared" in response.json()["message"]
    
    # Verify messages are cleared
    response = client.get(f"/messages/{conversation_id}")
    assert len(response.json()) == 0


@pytest.mark.message
def test_clear_messages_empty_conversation(client: TestClient, test_conversation):
    """Test clearing messages from already empty conversation."""
    response = client.delete(f"/messages/{test_conversation.id}")
    assert response.status_code == 200


@pytest.mark.message
def test_message_ordering(client: TestClient, test_conversation):
    """Test messages are ordered by creation time."""
    # Add multiple messages
    for i in range(3):
        response = client.post(
            f"/messages/{test_conversation.id}",
            json={"role": "user", "content": f"Message {i}"}
        )
        assert response.status_code == 200
    
    # Get messages
    response = client.get(f"/messages/{test_conversation.id}")
    data = response.json()
    
    # Should be ordered chronologically
    for i in range(len(data) - 1):
        assert data[i]["created_at"] <= data[i + 1]["created_at"]


@pytest.mark.message
def test_message_content_preserved(client: TestClient, test_conversation):
    """Test that message content is preserved exactly."""
    test_content = "This is a test message with special chars: !@#$%^&*()"
    response = client.post(
        f"/messages/{test_conversation.id}",
        json={"role": "user", "content": test_content}
    )
    assert response.status_code == 200
    
    # Retrieve and verify
    messages_response = client.get(f"/messages/{test_conversation.id}")
    messages = messages_response.json()
    assert messages[0]["content"] == test_content
