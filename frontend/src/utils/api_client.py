"""API client for communicating with backend."""
import requests
import json
from typing import Iterator, List, Optional
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEOUT = 60

class APIClient:
    """Simple HTTP client for backend API calls."""
    
    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip('/')
    
    def health_check(self) -> bool:
        """Check if backend is running."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    # ============================================================
    # Authentication
    # ============================================================
    
    def login(self, username: str, password: str) -> dict:
        """Login user."""
        try:
            response = requests.post(
                f"{self.base_url}/auth/login",
                json={"username": username, "password": password},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Login failed")}
        except Exception as e:
            return {"error": str(e)}
    
    def register(self, username: str, password: str) -> dict:
        """Register new user."""
        try:
            response = requests.post(
                f"{self.base_url}/auth/register",
                json={"username": username, "password": password},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("detail", "Registration failed")}
        except Exception as e:
            return {"error": str(e)}
    
    def get_users(self) -> list:
        """Get all users."""
        try:
            response = requests.get(f"{self.base_url}/auth/users", timeout=TIMEOUT)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================================
    # Conversations
    # ============================================================
    
    def get_conversations(self, username: str) -> list:
        """Get all conversations for a user."""
        try:
            response = requests.get(
                f"{self.base_url}/conversations/{username}",
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception as e:
            return []
    
    def create_conversation(self, username: str, title: str = "New Conversation") -> dict:
        """Create a new conversation."""
        try:
            response = requests.post(
                f"{self.base_url}/conversations/{username}",
                json={"title": title},
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def delete_conversation(self, conversation_id: int) -> dict:
        """Delete a conversation."""
        try:
            response = requests.delete(
                f"{self.base_url}/conversations/{conversation_id}",
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def update_conversation_title(self, conversation_id: int, title: str) -> dict:
        """Update conversation title."""
        try:
            response = requests.put(
                f"{self.base_url}/conversations/{conversation_id}/title",
                params={"title": title},
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================================
    # Messages
    # ============================================================
    
    def get_messages(self, conversation_id: int) -> list:
        """Get all messages in a conversation."""
        try:
            response = requests.get(
                f"{self.base_url}/messages/{conversation_id}",
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception as e:
            return []
    
    def add_message(self, conversation_id: int, role: str, content: str) -> dict:
        """Add a message to a conversation."""
        try:
            response = requests.post(
                f"{self.base_url}/messages/{conversation_id}",
                json={"role": role, "content": content},
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def clear_messages(self, conversation_id: int) -> dict:
        """Clear all messages in a conversation."""
        try:
            response = requests.delete(
                f"{self.base_url}/messages/{conversation_id}",
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================================
    # Chat
    # ============================================================
    
    def chat(self, query: str, user_id: str = "default") -> dict:
        """Send chat query."""
        try:
            response = requests.post(
                f"{self.base_url}/chat",
                json={"query": query, "user_id": user_id},
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def stream_chat(self, query: str, user_id: str = "default") -> Iterator[str]:
        """Stream chat response."""
        try:
            response = requests.post(
                f"{self.base_url}/stream",
                json={"query": query, "user_id": user_id},
                stream=True,
                timeout=TIMEOUT
            )
            for line in response.iter_lines():
                if line:
                    yield line.decode('utf-8')
        except Exception as e:
            yield json.dumps({"error": str(e)})
    
    # ============================================================
    # DSM-5 Tools
    # ============================================================
    
    def dsm5_search(self, query: str) -> dict:
        """Search DSM-5."""
        try:
            response = requests.post(
                f"{self.base_url}/dsm5/search",
                json={"query": query},
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def dsm5_hybrid_search(self, query: str, top_k: int = 5) -> dict:
        """Hybrid search in DSM-5."""
        try:
            response = requests.post(
                f"{self.base_url}/dsm5/hybrid",
                json={"query": query, "top_k": top_k},
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================================
    # Neo4j/Cypher Tools
    # ============================================================
    
    def cypher_query(self, query: str) -> dict:
        """Query hospital data."""
        try:
            response = requests.post(
                f"{self.base_url}/cypher/query",
                json={"query": query},
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def hospital_stats(self, query: str = "") -> dict:
        """Get hospital statistics."""
        try:
            response = requests.post(
                f"{self.base_url}/cypher/hospital-stats",
                json={"query": query},
                timeout=TIMEOUT
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}


# Global client instance
api_client = APIClient()
