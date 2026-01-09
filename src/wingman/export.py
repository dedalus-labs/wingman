"""Session export and import."""

import time
from pathlib import Path

from .lib import oj


def export_session_markdown(messages: list[dict], session_id: str | None = None) -> str:
    """Export session to markdown format."""
    lines = [f"# Chat Export{f': {session_id}' if session_id else ''}", ""]
    for msg in messages:
        role = msg.get("role", "unknown")
        if role not in ("user", "assistant"):
            continue

        # Handle segment-based format
        if "segments" in msg:
            parts = []
            for seg in msg["segments"]:
                if seg.get("type") == "text":
                    parts.append(seg.get("content", ""))
                elif seg.get("type") == "tool":
                    cmd = seg.get("command", "")
                    output = seg.get("output", "")
                    parts.append(f"\n```\n$ {cmd}\n→ {output}\n```\n")
            content = "".join(parts)
        else:
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                content = " ".join(text_parts) or "(image attachment)"

        if role == "user":
            lines.append(f"## User\n\n{content}\n")
        else:
            lines.append(f"## Assistant\n\n{content}\n")
    return "\n".join(lines)


def export_session_json(messages: list[dict], session_id: str | None = None) -> str:
    """Export session to JSON format."""
    export_data = {"session_id": session_id, "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"), "messages": messages}
    return oj.dumps(export_data, indent=2)


def import_session_from_file(path: Path) -> list[dict] | None:
    """Import session from markdown or JSON file."""
    if not path.exists():
        return None
    content = path.read_text()

    if path.suffix == ".json":
        try:
            data = oj.loads(content)
            if isinstance(data, dict) and "messages" in data:
                return data["messages"]
            if isinstance(data, list):
                return data
        except Exception:
            pass

    messages = []
    current_role = None
    current_content = []
    for line in content.split("\n"):
        if line.startswith("## User"):
            if current_role and current_content:
                messages.append({"role": current_role, "content": "\n".join(current_content).strip()})
            current_role = "user"
            current_content = []
        elif line.startswith("## Assistant"):
            if current_role and current_content:
                messages.append({"role": current_role, "content": "\n".join(current_content).strip()})
            current_role = "assistant"
            current_content = []
        elif current_role:
            current_content.append(line)
    if current_role and current_content:
        messages.append({"role": current_role, "content": "\n".join(current_content).strip()})
    return messages if messages else None
