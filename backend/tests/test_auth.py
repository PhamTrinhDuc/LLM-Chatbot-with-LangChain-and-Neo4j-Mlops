"""Tests for authentication endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.auth
def test_register_new_user(client: TestClient):
  """Test registering a new user."""
  response = client.post(
      "/auth/register",
      json={"username": "newuser", "password": "password123"}
  )
  assert response.status_code == 200
  data = response.json()
  assert data["username"] == "newuser"
  assert "user_id" in data


@pytest.mark.auth
def test_register_duplicate_user(client: TestClient, test_user):
  """Test registering with duplicate username fails."""
  response = client.post(
      "/auth/register",
      json={"username": "testuser", "password": "password123"}
  )
  assert response.status_code == 400
  assert "already exists" in response.json()["detail"]


@pytest.mark.auth
def test_login_valid_credentials(client: TestClient, test_user):
    """Test login with valid credentials."""
    response = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "user_id" in data


@pytest.mark.auth
def test_login_invalid_password(client: TestClient, test_user):
    """Test login with invalid password fails."""
    response = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


@pytest.mark.auth
def test_login_nonexistent_user(client: TestClient):
    """Test login with nonexistent user fails."""
    response = client.post(
        "/auth/login",
        json={"username": "nonexistent", "password": "password123"}
    )
    assert response.status_code == 401


@pytest.mark.auth
def test_get_all_users(client: TestClient, test_user, test_user_2):
    """Test retrieving all users."""
    response = client.get("/auth/users")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    usernames = [u["username"] for u in data]
    assert "testuser" in usernames
    assert "testuser2" in usernames