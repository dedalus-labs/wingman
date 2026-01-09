"""Session storage and persistence."""

from pathlib import Path

from .config import SESSIONS_DIR
from .lib import oj


def load_sessions() -> dict:
    """Load all sessions metadata."""
    path = SESSIONS_DIR / "sessions.json"
    if path.exists():
        return oj.loads(path.read_text())
    return {}


def save_sessions(sessions: dict) -> None:
    """Save sessions metadata."""
    path = SESSIONS_DIR / "sessions.json"
    path.write_text(oj.dumps(sessions, indent=2))


def get_session(session_id: str) -> list[dict]:
    """Load a specific session's messages."""
    data = load_sessions().get(session_id, [])
    # Handle new format (dict with messages/working_dir) vs old format (list)
    if isinstance(data, dict):
        return data.get("messages", [])
    return data


def get_session_working_dir(session_id: str) -> str | None:
    """Get the working directory for a session."""
    data = load_sessions().get(session_id)
    if isinstance(data, dict):
        return data.get("working_dir")
    return None


def save_session(session_id: str, messages: list[dict], working_dir: str | None = None) -> None:
    """Save a session's messages and optionally working directory."""
    sessions = load_sessions()
    existing = sessions.get(session_id)

    # Preserve existing working_dir if not provided
    if working_dir is None and isinstance(existing, dict):
        working_dir = existing.get("working_dir")

    # Store in new format
    sessions[session_id] = {"messages": messages, "working_dir": working_dir}
    save_sessions(sessions)


def save_session_working_dir(session_id: str, working_dir: str) -> None:
    """Save just the working directory for a session."""
    sessions = load_sessions()
    existing = sessions.get(session_id, {})

    if isinstance(existing, list):
        # Migrate from old format
        sessions[session_id] = {"messages": existing, "working_dir": working_dir}
    elif isinstance(existing, dict):
        existing["working_dir"] = working_dir
        sessions[session_id] = existing
    else:
        sessions[session_id] = {"messages": [], "working_dir": working_dir}

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
