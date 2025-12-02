"""Helper functions for chat UI."""
import json
from typing import Optional

def parse_stream_event(line: str) -> Optional[dict]:
    """Parse server-sent event."""
    try:
        if line.startswith("data: "):
            data = json.loads(line[6:])
            return data
    except:
        pass
    return None

def format_message(content: str, role: str = "user") -> dict:
    """Format message for display."""
    return {
        "role": role,
        "content": content
    }