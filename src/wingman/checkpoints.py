"""Checkpoint and rollback system."""

import difflib
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from .config import CHECKPOINTS_DIR
from .lib import oj

CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Checkpoint:
    """Snapshot of file states before edits."""

    id: str
    timestamp: float
    description: str
    files: dict[str, bytes]
    session_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "description": self.description,
            "file_paths": list(self.files.keys()),
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict, checkpoint_dir: Path) -> "Checkpoint":
        files = {}
        for fpath in data.get("file_paths", []):
            backup_file = checkpoint_dir / data["id"] / Path(fpath).name
            if backup_file.exists():
                files[fpath] = backup_file.read_bytes()
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            description=data["description"],
            files=files,
            session_id=data.get("session_id"),
        )


class CheckpointManager:
    """Manages file checkpoints for rollback capability."""

    def __init__(self, max_checkpoints: int = 50):
        self.max_checkpoints = max_checkpoints
        self._checkpoints: list[Checkpoint] = []
        self._counter = 0
        self._load_checkpoints()

    def _load_checkpoints(self) -> None:
        index_file = CHECKPOINTS_DIR / "index.json"
        if index_file.exists():
            try:
                data = oj.loads(index_file.read_text())
                self._checkpoints = [Checkpoint.from_dict(cp, CHECKPOINTS_DIR) for cp in data.get("checkpoints", [])]
                self._counter = data.get("counter", 0)
            except Exception:
                self._checkpoints = []

    def _save_index(self) -> None:
        index_file = CHECKPOINTS_DIR / "index.json"
        data = {
            "counter": self._counter,
            "checkpoints": [cp.to_dict() for cp in self._checkpoints],
        }
        index_file.write_text(oj.dumps(data, indent=2))

    def create(self, paths: list[Path], description: str = "", session_id: str | None = None) -> Checkpoint | None:
        files = {}
        for path in paths:
            if path.exists() and path.is_file():
                try:
                    files[str(path)] = path.read_bytes()
                except Exception:
                    continue

        if not files:
            return None

        self._counter += 1
        checkpoint_id = f"cp_{self._counter}"
        checkpoint = Checkpoint(
            id=checkpoint_id,
            timestamp=time.time(),
            description=description or f"Before edit: {paths[0].name}",
            files=files,
            session_id=session_id,
        )

        cp_dir = CHECKPOINTS_DIR / checkpoint_id
        cp_dir.mkdir(parents=True, exist_ok=True)
        for fpath, content in files.items():
            backup_file = cp_dir / Path(fpath).name
            backup_file.write_bytes(content)

        self._checkpoints.append(checkpoint)

        while len(self._checkpoints) > self.max_checkpoints:
            old = self._checkpoints.pop(0)
            old_dir = CHECKPOINTS_DIR / old.id
            if old_dir.exists():
                shutil.rmtree(old_dir)

        self._save_index()
        return checkpoint

    def restore(self, checkpoint_id: str) -> list[str]:
        checkpoint = next((cp for cp in self._checkpoints if cp.id == checkpoint_id), None)
        if not checkpoint:
            return []

        restored = []
        for fpath, content in checkpoint.files.items():
            try:
                Path(fpath).write_bytes(content)
                restored.append(fpath)
            except Exception:
                continue

        if restored:
            self._remove_checkpoint(checkpoint_id)

        return restored

    def _remove_checkpoint(self, checkpoint_id: str) -> None:
        """Remove a checkpoint after rollback (user is now at that state)."""
        idx = next((i for i, cp in enumerate(self._checkpoints) if cp.id == checkpoint_id), None)
        if idx is None:
            return

        cp = self._checkpoints.pop(idx)
        cp_dir = CHECKPOINTS_DIR / cp.id
        if cp_dir.exists():
            shutil.rmtree(cp_dir)

        self._save_index()

    def list_recent(self, n: int = 10, session_id: str | None = None) -> list[Checkpoint]:
        if not session_id:
            return []
        filtered = [cp for cp in self._checkpoints if cp.session_id == session_id]
        return list(reversed(filtered[-n:]))

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        return next((cp for cp in self._checkpoints if cp.id == checkpoint_id), None)

    def diff(self, checkpoint_id: str) -> dict[str, str]:
        checkpoint = self.get(checkpoint_id)
        if not checkpoint:
            return {}

        diffs = {}
        for fpath, old_content in checkpoint.files.items():
            path = Path(fpath)
            if not path.exists():
                diffs[fpath] = f"[File deleted: {fpath}]"
                continue
            try:
                new_content = path.read_bytes()
                if old_content == new_content:
                    continue
                old_lines = old_content.decode(errors="replace").splitlines(keepends=True)
                new_lines = new_content.decode(errors="replace").splitlines(keepends=True)
                diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path.name}", tofile=f"b/{path.name}")
                diffs[fpath] = "".join(diff)
            except Exception as e:
                diffs[fpath] = f"[Error reading {fpath}: {e}]"
        return diffs


# Global state
_checkpoint_manager: CheckpointManager | None = None
_current_session_id: str | None = None


def get_checkpoint_manager() -> CheckpointManager:
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager


def set_current_session(session_id: str | None) -> None:
    global _current_session_id
    _current_session_id = session_id


def get_current_session() -> str | None:
    return _current_session_id
