"""Project memory persistence."""

import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import CONFIG_DIR
from .lib import oj


@dataclass
class MemoryEntry:
    """A single memory note."""

    id: str
    content: str
    created_at: float

    @classmethod
    def create(cls, content: str) -> "MemoryEntry":
        """Create entry with generated ID and current timestamp."""
        return cls(id=uuid.uuid4().hex[:8], content=content, created_at=time.time())


@dataclass
class ProjectMemory:
    """Memory store for a project directory."""

    entries: list[MemoryEntry]
    version: int = 1


def _get_memory_path() -> Path:
    """Path for current directory's memory file."""
    memory_dir = CONFIG_DIR / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    cwd_hash = str(Path.cwd()).replace("/", "_").replace("\\", "_")
    return memory_dir / f"{cwd_hash}.json"


def _migrate_md_to_json(md_path: Path) -> ProjectMemory:
    """Migrate old .md format to new .json format."""
    content = md_path.read_text().strip()
    if not content:
        md_path.unlink()
        return ProjectMemory(entries=[])

    # Split by double newlines, each becomes an entry
    chunks = [c.strip() for c in content.split("\n\n") if c.strip()]
    entries = [MemoryEntry.create(c) for c in chunks]
    md_path.unlink()
    return ProjectMemory(entries=entries)


def load_memory() -> ProjectMemory:
    """Load memory for current directory."""
    json_path = _get_memory_path()
    md_path = json_path.with_suffix(".md")

    # Auto-migrate if old format exists
    if md_path.exists() and not json_path.exists():
        mem = _migrate_md_to_json(md_path)
        save_memory(mem)
        return mem

    if json_path.exists():
        try:
            data = oj.loads(json_path.read_text())
            entries = [MemoryEntry(**e) for e in data.get("entries", [])]
            return ProjectMemory(entries=entries, version=data.get("version", 1))
        except Exception:
            return ProjectMemory(entries=[])

    return ProjectMemory(entries=[])


def save_memory(memory: ProjectMemory) -> None:
    """Save memory to disk."""
    path = _get_memory_path()
    data = {"version": memory.version, "entries": [asdict(e) for e in memory.entries]}
    path.write_text(oj.dumps(data, indent=2))


def add_entry(content: str) -> MemoryEntry:
    """Add a new memory entry."""
    memory = load_memory()
    entry = MemoryEntry.create(content)
    memory.entries.append(entry)
    save_memory(memory)
    return entry


def delete_entries(entry_ids: list[str]) -> int:
    """Delete entries by ID. Returns count deleted."""
    memory = load_memory()
    before = len(memory.entries)
    memory.entries = [e for e in memory.entries if e.id not in entry_ids]
    after = len(memory.entries)
    save_memory(memory)
    return before - after


def clear_all() -> None:
    """Delete all entries."""
    save_memory(ProjectMemory(entries=[]))
