"""Tests for conversation management endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.conversation
def test_create_conversation(client: TestClient, test_user):
    """Test creating a new conversation."""
    response = client.post(
        f"/conversations/{test_user.username}",
        json={"title": "My First Chat"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "My First Chat"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.conversation
def test_create_conversation_default_title(client: TestClient, test_user):
    """Test creating conversation with default title."""
    response = client.post(
        f"/conversations/{test_user.username}",
        json={}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Conversation"


@pytest.mark.conversation
def test_create_conversation_nonexistent_user(client: TestClient):
    """Test creating conversation for nonexistent user fails."""
    response = client.post(
        "/conversations/nonexistentuser",
        json={"title": "Test Chat"}
    )
    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


@pytest.mark.conversation
def test_get_conversations(client: TestClient, test_user, test_conversation):
    """Test retrieving user's conversations."""
    response = client.get(f"/conversations/{test_user.username}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(c["id"] == test_conversation.id for c in data)


@pytest.mark.conversation
def test_get_conversations_empty(client: TestClient, test_user_2):
    """Test retrieving conversations for user with no conversations."""
    response = client.get(f"/conversations/{test_user_2.username}")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.conversation
def test_delete_conversation(client: TestClient, test_conversation):
    """Test deleting a conversation."""
    response = client.delete(f"/conversations/{test_conversation.id}")
    assert response.status_code == 200
    assert "deleted" in response.json()["message"]


@pytest.mark.conversation
def test_delete_nonexistent_conversation(client: TestClient):
    """Test deleting nonexistent conversation fails."""
    response = client.delete("/conversations/9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.conversation
def test_update_conversation_title(client: TestClient, test_conversation):
    """Test updating conversation title."""
    new_title = "Updated Title"
    response = client.put(
        f"/conversations/{test_conversation.id}/title",
        params={"title": new_title}
    )
    assert response.status_code == 200
    assert response.json()["title"] == new_title


@pytest.mark.conversation
def test_update_nonexistent_conversation_title(client: TestClient):
    """Test updating nonexistent conversation title fails."""
    response = client.put(
        "/conversations/9999/title",
        params={"title": "New Title"}
    )
    assert response.status_code == 404


@pytest.mark.conversation
def test_conversation_ordering(client: TestClient, test_user, db):
    """Test conversations are ordered by recent first."""
    # Create multiple conversations
    for i in range(3):
        response = client.post(
            f"/conversations/{test_user.username}",
            json={"title": f"Chat {i}"}
        )
        assert response.status_code == 200
    
    # Get conversations
    response = client.get(f"/conversations/{test_user.username}")
    data = response.json()
    
    # Should be ordered by updated_at descending
    for i in range(len(data) - 1):
        assert data[i]["updated_at"] >= data[i + 1]["updated_at"]
