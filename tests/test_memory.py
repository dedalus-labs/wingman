"""Tests for memory system."""

import json
import time

import pytest

from wingman.memory import (
    MemoryEntry,
    ProjectMemory,
    add_entry,
    clear_all,
    delete_entries,
    load_memory,
    save_memory,
)


@pytest.fixture
def memory_dir(tmp_path, monkeypatch):
    """Redirect memory storage to temp directory."""
    config_dir = tmp_path / ".wingman"
    config_dir.mkdir()
    monkeypatch.setattr("wingman.memory.CONFIG_DIR", config_dir)
    # Also set cwd so hash is consistent
    monkeypatch.chdir(tmp_path)
    return config_dir / "memory"


class TestMemoryEntry:
    """Test MemoryEntry dataclass."""

    def test_create_generates_id(self):
        """create() generates unique 8-char ID."""
        e1 = MemoryEntry.create("test content")
        e2 = MemoryEntry.create("test content")
        assert len(e1.id) == 8
        assert e1.id != e2.id

    def test_create_sets_timestamp(self):
        """create() sets timestamp to now."""
        before = time.time()
        entry = MemoryEntry.create("test")
        after = time.time()
        assert before <= entry.created_at <= after

    def test_content_preserved(self):
        """Content is stored exactly."""
        content = "Multi\nline\ncontent with [special] chars"
        entry = MemoryEntry.create(content)
        assert entry.content == content


class TestProjectMemory:
    """Test ProjectMemory container."""

    def test_empty_default(self):
        """New memory has empty entries."""
        mem = ProjectMemory(entries=[])
        assert mem.entries == []
        assert mem.version == 1

    def test_with_entries(self):
        """Can hold multiple entries."""
        entries = [MemoryEntry.create("a"), MemoryEntry.create("b")]
        mem = ProjectMemory(entries=entries)
        assert len(mem.entries) == 2


class TestPersistence:
    """Test save/load cycle."""

    def test_roundtrip(self, memory_dir):
        """Save then load returns same data."""
        entry = MemoryEntry(id="abc123", content="test note", created_at=1234567890.5)
        mem = ProjectMemory(entries=[entry])
        save_memory(mem)

        loaded = load_memory()
        assert len(loaded.entries) == 1
        assert loaded.entries[0].id == "abc123"
        assert loaded.entries[0].content == "test note"
        assert loaded.entries[0].created_at == 1234567890.5

    def test_load_empty(self, memory_dir):
        """Load with no file returns empty memory."""
        mem = load_memory()
        assert mem.entries == []

    def test_storage_format(self, memory_dir):
        """Verify JSON structure on disk."""
        entry = MemoryEntry(id="test", content="note", created_at=1000.0)
        save_memory(ProjectMemory(entries=[entry]))

        # Find the saved file
        files = list(memory_dir.glob("*.json"))
        assert len(files) == 1

        data = json.loads(files[0].read_text())
        assert data["version"] == 1
        assert len(data["entries"]) == 1
        assert data["entries"][0]["id"] == "test"
        assert data["entries"][0]["content"] == "note"


class TestOperations:
    """Test CRUD operations."""

    def test_add_entry(self, memory_dir):
        """add_entry creates and persists entry."""
        entry = add_entry("my note")
        assert entry.content == "my note"
        assert len(entry.id) == 8

        # Verify persisted
        mem = load_memory()
        assert len(mem.entries) == 1
        assert mem.entries[0].id == entry.id

    def test_add_multiple(self, memory_dir):
        """Multiple adds accumulate."""
        add_entry("first")
        add_entry("second")
        add_entry("third")

        mem = load_memory()
        assert len(mem.entries) == 3

    def test_delete_single(self, memory_dir):
        """Delete removes by ID."""
        e1 = add_entry("keep")
        e2 = add_entry("delete")

        count = delete_entries([e2.id])
        assert count == 1

        mem = load_memory()
        assert len(mem.entries) == 1
        assert mem.entries[0].id == e1.id

    def test_delete_multiple(self, memory_dir):
        """Delete multiple at once."""
        entries = [add_entry(f"note {i}") for i in range(5)]
        to_delete = [entries[1].id, entries[3].id]

        count = delete_entries(to_delete)
        assert count == 2

        mem = load_memory()
        assert len(mem.entries) == 3
        remaining_ids = {e.id for e in mem.entries}
        assert entries[1].id not in remaining_ids
        assert entries[3].id not in remaining_ids

    def test_delete_nonexistent(self, memory_dir):
        """Deleting nonexistent ID returns 0."""
        add_entry("existing")
        count = delete_entries(["nonexistent"])
        assert count == 0

    def test_clear_all(self, memory_dir):
        """clear_all removes everything."""
        for i in range(5):
            add_entry(f"note {i}")

        clear_all()
        mem = load_memory()
        assert len(mem.entries) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_corrupted_json(self, memory_dir, monkeypatch, tmp_path):
        """Corrupted JSON returns empty memory."""
        monkeypatch.chdir(tmp_path)
        memory_dir.mkdir(parents=True, exist_ok=True)

        cwd_hash = str(tmp_path).replace("/", "_").replace("\\", "_")
        json_path = memory_dir / f"{cwd_hash}.json"
        json_path.write_text("not valid json {{{")

        mem = load_memory()
        assert mem.entries == []

    def test_unicode_content(self, memory_dir):
        """Unicode in content is preserved."""
        content = "日本語 emoji 🎉 and symbols →←"
        entry = add_entry(content)
        assert entry.content == content

        mem = load_memory()
        assert mem.entries[0].content == content

    def test_multiline_content(self, memory_dir):
        """Multiline content in single entry."""
        content = "Line 1\nLine 2\nLine 3"
        add_entry(content)

        mem = load_memory()
        assert mem.entries[0].content == content
