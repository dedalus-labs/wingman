"""Session storage and persistence."""

import json
from pathlib import Path

from .config import SESSIONS_DIR


def load_sessions() -> dict:
    """Load all sessions metadata."""
    path = SESSIONS_DIR / "sessions.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_sessions(sessions: dict) -> None:
    """Save sessions metadata."""
    path = SESSIONS_DIR / "sessions.json"
    path.write_text(json.dumps(sessions, indent=2))


def get_session(session_id: str) -> list[dict]:
    """Load a specific session's messages."""
    return load_sessions().get(session_id, [])


def save_session(session_id: str, messages: list[dict]) -> None:
    """Save a session's messages."""
    sessions = load_sessions()
    sessions[session_id] = messages
    save_sessions(sessions)


def delete_session(session_id: str) -> None:
    """Delete a session."""
    sessions = load_sessions()
    sessions.pop(session_id, None)
    save_sessions(sessions)


def rename_session(old_id: str, new_id: str) -> bool:
    """Rename a session."""
    sessions = load_sessions()
    if old_id in sessions:
        sessions[new_id] = sessions.pop(old_id)
        save_sessions(sessions)
        return True
    return False
