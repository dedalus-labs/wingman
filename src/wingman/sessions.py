"""Session storage and persistence."""

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


def get_session_parent(session_id: str) -> str | None:
    """Return the parent session_id if this session is a fork, else None."""
    data = load_sessions().get(session_id)
    if isinstance(data, dict):
        return data.get("parent_session_id")
    return None


def save_session(
    session_id: str,
    messages: list[dict],
    working_dir: str | None = None,
    parent_session_id: str | None = None,
    forked_at_index: int | None = None,
) -> None:
    """Save a session's messages and optionally working directory and fork lineage."""
    sessions = load_sessions()
    existing = sessions.get(session_id)

    # Preserve existing fields if not provided.
    if working_dir is None and isinstance(existing, dict):
        working_dir = existing.get("working_dir")
    if parent_session_id is None and isinstance(existing, dict):
        parent_session_id = existing.get("parent_session_id")
    if forked_at_index is None and isinstance(existing, dict):
        forked_at_index = existing.get("forked_at_index")

    entry: dict = {"messages": messages, "working_dir": working_dir}
    if parent_session_id is not None:
        entry["parent_session_id"] = parent_session_id
    if forked_at_index is not None:
        entry["forked_at_index"] = forked_at_index

    sessions[session_id] = entry
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


def list_forks(parent_session_id: str) -> list[str]:
    """Return session_ids whose parent_session_id matches."""
    sessions = load_sessions()
    forks: list[str] = []
    for sid, data in sessions.items():
        if isinstance(data, dict) and data.get("parent_session_id") == parent_session_id:
            forks.append(sid)
    return forks


def get_fork_points(parent_session_id: str) -> list[tuple[str, int]]:
    """Return (fork_session_id, forked_at_index) pairs for all children.

    Used by the scrollback to render BranchMarker widgets at the divergence
    point of each fork. Skips forks that are missing forked_at_index.
    """
    sessions = load_sessions()
    points: list[tuple[str, int]] = []
    for sid, data in sessions.items():
        if not isinstance(data, dict):
            continue
        if data.get("parent_session_id") != parent_session_id:
            continue
        idx = data.get("forked_at_index")
        if idx is None:
            continue
        points.append((sid, int(idx)))
    return points


def fork_session_copy(
    new_id: str,
    messages: list[dict],
    parent_session_id: str | None,
    forked_at_index: int,
    working_dir: str | None = None,
) -> bool:
    """Create a new session with a copied slice of messages and parent linkage.

    Returns False if new_id already exists. Caller is responsible for slicing
    messages to the desired fork point.
    """
    sessions = load_sessions()
    if new_id in sessions:
        return False
    sessions[new_id] = {
        "messages": list(messages),
        "working_dir": working_dir,
        "parent_session_id": parent_session_id,
        "forked_at_index": forked_at_index,
    }
    save_sessions(sessions)
    return True
