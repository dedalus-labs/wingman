"""Dynamic messaging system for banners, tips, and notices."""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
import yaml

from .config import APP_VERSION, CONFIG_DIR
from .lib import oj

# URLs and paths
REMOTE_BASE = "https://raw.githubusercontent.com/dedalus-labs/wingman/main/bulletin"
CACHE_DIR = CONFIG_DIR / "bulletin_cache"
DISMISSED_FILE = CONFIG_DIR / "bulletin_dismissed.json"

CACHE_TTL = 3600


def _get_bulletin_dir() -> Path | None:
    """Get local bulletin directory if available."""
    # Explicit override
    if path := os.environ.get("WINGMAN_BULLETIN_PATH"):
        p = Path(path)
        if p.is_dir():
            return p

    # Dev mode env var
    if os.environ.get("WINGMAN_DEV"):
        for candidate in [Path.cwd() / "bulletin", Path(__file__).parent.parent.parent / "bulletin"]:
            if candidate.is_dir():
                return candidate

    # Auto-detect editable install
    local = Path(__file__).parent.parent.parent / "bulletin"
    if local.is_dir() and (local / "banners.yml").exists():
        return local

    return None


def is_dev_mode() -> bool:
    """Check if local bulletin files are available."""
    return _get_bulletin_dir() is not None


@dataclass
class Conditions:
    """When to show a bulletin."""

    from_time: datetime | None = None
    until: datetime | None = None
    version_lt: str | None = None
    version_gte: str | None = None
    first_run: bool = False
    platforms: list[str] = field(default_factory=list)


@dataclass
class Action:
    """Optional action button."""

    label: str = ""
    url: str | None = None
    command: str | None = None


@dataclass
class Bulletin:
    """A single message."""

    id: str
    type: Literal["banner", "tip", "notice", "modal"]
    content: str
    conditions: Conditions | None = None
    priority: int = 0
    dismissible: bool = True
    dismiss_persist: bool = False
    action: Action | None = None


def _parse_conditions(data: dict | None) -> Conditions | None:
    if not data:
        return None
    return Conditions(
        from_time=datetime.fromisoformat(data["from"]) if data.get("from") else None,
        until=datetime.fromisoformat(data["until"]) if data.get("until") else None,
        version_lt=data.get("version_lt"),
        version_gte=data.get("version_gte"),
        first_run=data.get("first_run", False),
        platforms=data.get("platforms", []),
    )


def _parse_action(data: dict | None) -> Action | None:
    if not data:
        return None
    return Action(label=data.get("label", ""), url=data.get("url"), command=data.get("command"))


def _parse_bulletin(data: dict) -> Bulletin | None:
    try:
        return Bulletin(
            id=data["id"],
            type=data["type"],
            content=data["content"],
            conditions=_parse_conditions(data.get("conditions")),
            priority=data.get("priority", 0),
            dismissible=data.get("dismissible", True),
            dismiss_persist=data.get("dismiss_persist", False),
            action=_parse_action(data.get("action")),
        )
    except (KeyError, ValueError):
        return None


def _compare_versions(v1: str, v2: str) -> int:
    """Compare semver versions. Returns -1, 0, or 1."""

    def parts(v: str) -> list[int]:
        p = [int(x) for x in v.split(".")[:3]]
        while len(p) < 3:
            p.append(0)
        return p

    for a, b in zip(parts(v1), parts(v2), strict=True):
        if a < b:
            return -1
        if a > b:
            return 1
    return 0


def evaluate_conditions(conditions: Conditions | None) -> bool:
    """Check if conditions are met."""
    if conditions is None:
        return True

    now = datetime.now(timezone.utc)

    if conditions.from_time:
        t = conditions.from_time
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if now < t:
            return False

    if conditions.until:
        t = conditions.until
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if now > t:
            return False

    if conditions.version_lt and _compare_versions(APP_VERSION, conditions.version_lt) >= 0:
        return False

    if conditions.version_gte and _compare_versions(APP_VERSION, conditions.version_gte) < 0:
        return False

    if conditions.platforms and sys.platform not in conditions.platforms:
        return False

    return True


def load_from_yaml(content: str) -> list[Bulletin]:
    """Parse bulletins from YAML content."""
    try:
        data = yaml.safe_load(content)
        if not data or not data.get("messages"):
            return []
        return [b for msg in data["messages"] if (b := _parse_bulletin(msg))]
    except yaml.YAMLError:
        return []


def load_local(category: str) -> list[Bulletin]:
    """Load bulletins from local file."""
    local_dir = _get_bulletin_dir()
    if not local_dir:
        return []

    yaml_file = local_dir / f"{category}.yml"
    if not yaml_file.exists():
        return []

    try:
        return load_from_yaml(yaml_file.read_text())
    except Exception:
        return []


async def fetch_remote(category: str) -> list[Bulletin]:
    """Fetch bulletins from GitHub."""
    url = f"{REMOTE_BASE}/{category}.yml"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return load_from_yaml(resp.text)
    except Exception:
        pass
    return []


class BulletinManager:
    """Manages bulletin fetching, caching, and dismissal."""

    def __init__(self):
        self._dismissed: set[str] = set()
        self._loaded: dict[str, list[Bulletin]] = {}
        self._load_dismissed()

    def _load_dismissed(self) -> None:
        if DISMISSED_FILE.exists():
            try:
                data = oj.loads(DISMISSED_FILE.read_text())
                self._dismissed = set(data.get("dismissed", []))
            except Exception:
                pass

    def _save_dismissed(self) -> None:
        DISMISSED_FILE.parent.mkdir(parents=True, exist_ok=True)
        DISMISSED_FILE.write_text(oj.dumps({"dismissed": list(self._dismissed)}))

    def dismiss(self, bulletin_id: str, persist: bool = False) -> None:
        """Dismiss a bulletin."""
        self._dismissed.add(bulletin_id)
        if persist:
            self._save_dismissed()

    def is_dismissed(self, bulletin_id: str) -> bool:
        return bulletin_id in self._dismissed

    def get_active(self, category: str, include_dismissed: bool = False) -> list[Bulletin]:
        """Get bulletins that should be shown, sorted by priority."""
        bulletins = self._loaded.get(category, [])
        active = [
            b
            for b in bulletins
            if (include_dismissed or not self.is_dismissed(b.id)) and evaluate_conditions(b.conditions)
        ]
        return sorted(active, key=lambda b: b.priority, reverse=True)

    def load_sync(self, category: str) -> list[Bulletin]:
        """Load bulletins synchronously (dev mode only)."""
        if is_dev_mode():
            self._loaded[category] = load_local(category)
            return self._loaded[category]
        return []

    async def load_async(self, category: str) -> list[Bulletin]:
        """Load bulletins asynchronously."""
        if is_dev_mode():
            self._loaded[category] = load_local(category)
        else:
            self._loaded[category] = await fetch_remote(category)
        return self._loaded[category]


# Global instance
_manager: BulletinManager | None = None


def get_bulletin_manager() -> BulletinManager:
    """Get the global bulletin manager."""
    global _manager
    if _manager is None:
        _manager = BulletinManager()
    return _manager
