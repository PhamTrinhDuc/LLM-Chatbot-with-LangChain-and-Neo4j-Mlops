"""Integration tests combining multiple features."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_full_user_flow(client: TestClient):
    """Test complete user flow: register -> login -> create conversation."""
    # Register
    register_response = client.post(
        "/auth/register",
        json={"username": "flowuser", "password": "password123"}
    )
    assert register_response.status_code == 200
    
    # Login
    login_response = client.post(
        "/auth/login",
        json={"username": "flowuser", "password": "password123"}
    )
    assert login_response.status_code == 200
    
    # Create conversation
    conv_response = client.post(
        "/conversations/flowuser",
        json={"title": "Test Flow"}
    )
    assert conv_response.status_code == 200
    conv_id = conv_response.json()["id"]
    
    # Add message
    msg_response = client.post(
        f"/messages/{conv_id}",
        json={"role": "user", "content": "Hello"}
    )
    assert msg_response.status_code == 200
    
    # Retrieve messages
    get_response = client.get(f"/messages/{conv_id}")
    assert get_response.status_code == 200
    assert len(get_response.json()) == 1


@pytest.mark.integration
def test_conversation_lifecycle(client: TestClient, test_user):
    """Test complete conversation lifecycle."""
    # Create
    create_response = client.post(
        f"/conversations/{test_user.username}",
        json={"title": "Lifecycle Test"}
    )
    assert create_response.status_code == 200
    conv_id = create_response.json()["id"]
    
    # Add messages
    for i in range(3):
        response = client.post(
            f"/messages/{conv_id}",
            json={"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
        )
        assert response.status_code == 200
    
    # Get messages
    get_response = client.get(f"/messages/{conv_id}")
    assert len(get_response.json()) == 3
    
    # Update title
    update_response = client.put(
        f"/conversations/{conv_id}/title",
        params={"title": "Updated Title"}
    )
    assert update_response.status_code == 200
    
    # Clear messages
    clear_response = client.delete(f"/messages/{conv_id}")
    assert clear_response.status_code == 200
    
    # Verify messages cleared
    get_response = client.get(f"/messages/{conv_id}")
    assert len(get_response.json()) == 0
    
    # Delete conversation
    delete_response = client.delete(f"/conversations/{conv_id}")
    assert delete_response.status_code == 200


@pytest.mark.integration
def test_multiple_conversations_isolation(client: TestClient, test_user):
    """Test that multiple conversations are isolated."""
    # Create first conversation
    conv1_response = client.post(
        f"/conversations/{test_user.username}",
        json={"title": "Conv 1"}
    )
    conv1_id = conv1_response.json()["id"]
    
    # Create second conversation
    conv2_response = client.post(
        f"/conversations/{test_user.username}",
        json={"title": "Conv 2"}
    )
    conv2_id = conv2_response.json()["id"]
    
    # Add messages to first conversation
    client.post(
        f"/messages/{conv1_id}",
        json={"role": "user", "content": "Conv 1 Message"}
    )
    
    # Add messages to second conversation
    client.post(
        f"/messages/{conv2_id}",
        json={"role": "user", "content": "Conv 2 Message"}
    )
    
    # Verify isolation
    conv1_msgs = client.get(f"/messages/{conv1_id}").json()
    conv2_msgs = client.get(f"/messages/{conv2_id}").json()
    
    assert len(conv1_msgs) == 1
    assert len(conv2_msgs) == 1
    assert conv1_msgs[0]["content"] == "Conv 1 Message"
    assert conv2_msgs[0]["content"] == "Conv 2 Message"
