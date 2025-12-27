"""Project memory persistence."""

from pathlib import Path

from .config import CONFIG_DIR


def get_memory_path() -> Path:
    """Get memory file path for current working directory."""
    memory_dir = CONFIG_DIR / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    cwd_hash = str(Path.cwd()).replace("/", "_").replace("\\", "_")
    return memory_dir / f"{cwd_hash}.md"


def load_memory() -> str:
    """Load project memory for current directory."""
    path = get_memory_path()
    if path.exists():
        return path.read_text()
    return ""


def save_memory(content: str) -> None:
    """Save project memory."""
    get_memory_path().write_text(content)


def append_memory(text: str) -> None:
    """Append to project memory."""
    current = load_memory()
    new_content = current + "\n\n" + text if current else text
    save_memory(new_content)


def clear_memory() -> None:
    """Clear project memory."""
    path = get_memory_path()
    if path.exists():
        path.unlink()
