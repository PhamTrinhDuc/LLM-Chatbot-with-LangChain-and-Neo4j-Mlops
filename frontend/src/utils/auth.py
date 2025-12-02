"""Authentication utilities for frontend."""
from src.utils.api_client import api_client
from typing import Tuple


def login_user(username: str, password: str) -> Tuple[bool, str]:
    """
    Login user via API.
    
    Returns:
        Tuple of (success, message)
    """
    if not username or not password:
        return False, "Please enter username and password"
    
    try:
        response = api_client.login(username, password)
        
        if "error" in response:
            return False, response.get("detail", response["error"])
        
        return True, f"Welcome back, {username}!"
    
    except Exception as e:
        return False, f"Login failed: {str(e)}"


def register_user(username: str, password: str) -> Tuple[bool, str]:
    """
    Register new user via API.
    
    Returns:
        Tuple of (success, message)
    """
    if not username or not password:
        return False, "Please enter username and password"
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(password) < 4:
        return False, "Password must be at least 4 characters"
    
    try:
        response = api_client.register(username, password)
        
        if "error" in response:
            return False, response.get("detail", response["error"])
        
        return True, "Registration successful! Please login."
    
    except Exception as e:
        return False, f"Registration failed: {str(e)}"


def get_users_list() -> list:
    """Get list of all users (for debugging)."""
    try:
        response = api_client.get_users()
        if "error" in response:
            return []
        return response
    except:
        return []
