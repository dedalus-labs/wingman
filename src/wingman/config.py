"""Configuration and constants."""

import contextlib
from importlib.metadata import version
from pathlib import Path

import httpx

from .lib import oj

# Paths
CONFIG_DIR = Path.home() / ".wingman"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"
CHECKPOINTS_DIR = CONFIG_DIR / "checkpoints"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# App metadata
APP_NAME = "Wingman"
APP_VERSION = version("wingman-cli")
APP_CREDIT = "Dedalus Labs"

# API
DEDALUS_SITE_URL = "https://dedaluslabs.ai"


# Models are populated at runtime by fetching from {base_url}/v1/models.
# Empty until the client is initialized; /model picker errors out until then.
MODELS: list[str] = []
MARKETPLACE_SERVERS: list[dict] = []

# Commands for autocomplete (command, description)
COMMANDS = [
    ("/new", "Start new chat"),
    ("/rename", "Rename session"),
    ("/delete", "Delete session"),
    ("/split", "Split panel"),
    ("/close", "Close panel"),
    ("/model", "Switch model"),
    ("/code", "Toggle coding mode"),
    ("/cd", "Change directory"),
    ("/ls", "List files"),
    ("/ps", "List processes"),
    ("/kill", "Stop process"),
    ("/history", "View checkpoints"),
    ("/rollback", "Restore checkpoint"),
    ("/diff", "Show changes"),
    ("/compact", "Compact context"),
    ("/context", "Context usage"),
    ("/mcp", "MCP servers"),
    ("/memory", "Project memory"),
    ("/export", "Export session"),
    ("/import", "Import file"),
    ("/fork", "Fork session (optionally rewind N turns)"),
    ("/forks", "List forks of this session"),
    ("/key", "API key"),
    ("/base_url", "API base URL"),
    ("/clear", "Clear chat"),
    ("/help", "Show help"),
    ("/exit", "Quit Wingman"),
    ("/bug", "Report a bug"),
    ("/feature", "Request feature"),
]

# Options for command completion (first argument only).
COMMAND_OPTIONS: dict[str, list[str]] = {
    "export": ["json"],
    "memory": ["add", "clear", "delete", "help"],
    "mcp": ["clear"],
}


def load_api_key() -> str | None:
    """Load API key from config file."""
    if CONFIG_FILE.exists():
        try:
            config = oj.loads(CONFIG_FILE.read_text())
            return config.get("api_key")
        except Exception:
            pass
    return None


def load_base_url() -> str | None:
    """Load API base URL from environment or config.

    Checks ``BASE_URL`` env var first, then ``base_url`` in
    ``~/.wingman/config.json``. Auto-prepends ``https://`` if the value
    has no scheme so a bare host like ``preview.api.dedaluslabs.ai``
    doesn't crash the URL parser. Returns None to use the SDK default.

    Returns:
        Base URL string or None.

    """
    import os

    raw = os.environ.get("BASE_URL")
    if not raw and CONFIG_FILE.exists():
        try:
            config = oj.loads(CONFIG_FILE.read_text())
            raw = config.get("base_url")
        except Exception:
            pass
    if not raw:
        return None
    raw = raw.rstrip("/")
    if "://" not in raw:
        raw = f"https://{raw}"
    return raw


def save_api_key(api_key: str) -> None:
    """Save API key to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {}
    if CONFIG_FILE.exists():
        with contextlib.suppress(Exception):
            config = oj.loads(CONFIG_FILE.read_text())
    config["api_key"] = api_key
    CONFIG_FILE.write_text(oj.dumps(config, indent=2))


def save_base_url(base_url: str | None) -> None:
    """Save (or clear) the base_url in the config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {}
    if CONFIG_FILE.exists():
        with contextlib.suppress(Exception):
            config = oj.loads(CONFIG_FILE.read_text())
    if base_url:
        config["base_url"] = base_url.rstrip("/")
    else:
        config.pop("base_url", None)
    CONFIG_FILE.write_text(oj.dumps(config, indent=2))


def base_url_in_config() -> bool:
    """True iff base_url is explicitly set in ~/.wingman/config.json."""
    if not CONFIG_FILE.exists():
        return False
    try:
        config = oj.loads(CONFIG_FILE.read_text())
        return bool(config.get("base_url"))
    except Exception:
        return False


INSTRUCTION_FILENAMES = ["AGENTS.md", "WINGMAN.md"]
MAX_INSTRUCTION_BYTES = 32 * 1024  # 32KB limit per file


def load_instructions(working_dir: Path | None = None) -> str:
    """Load custom instructions from global and local sources.

    Searches for AGENTS.md or WINGMAN.md (first found wins) in:
    - Global: ~/.wingman/ (user-level preferences, higher priority)
    - Local: {working_dir}/ (project-specific context)

    Returns combined instructions with hierarchy framing, or empty string if none found.
    """
    global_content: str | None = None
    local_content: str | None = None

    # Global instructions (~/.wingman/AGENTS.md or WINGMAN.md)
    for name in INSTRUCTION_FILENAMES:
        global_path = CONFIG_DIR / name
        try:
            if global_path.is_file():
                content = global_path.read_text("utf-8", errors="ignore")[:MAX_INSTRUCTION_BYTES]
                if content.strip():
                    global_content = content.strip()
                    break
        except OSError:
            continue

    # Local instructions ({working_dir}/AGENTS.md or WINGMAN.md)
    if working_dir:
        for name in INSTRUCTION_FILENAMES:
            local_path = working_dir / name
            try:
                if local_path.is_file():
                    content = local_path.read_text("utf-8", errors="ignore")[:MAX_INSTRUCTION_BYTES]
                    if content.strip():
                        local_content = content.strip()
                        break
            except OSError:
                continue

    # Combine with hierarchy framing
    if not global_content and not local_content:
        return ""

    sections: list[str] = ["## Custom Instructions"]

    if global_content and local_content:
        sections.append(
            "The following instructions are provided at two levels. "
            "Global instructions (from ~/.wingman/) represent the user's general preferences and take precedence. "
            "Project instructions (from .wingman/) provide local context but should not override global directives."
        )
        sections.append(f"### Global Instructions (Higher Priority)\n{global_content}")
        sections.append(f"### Project Instructions (Local Context)\n{local_content}")
    elif global_content:
        sections.append(f"### Global Instructions\n{global_content}")
    else:
        sections.append(f"### Project Instructions\n{local_content}")

    return "\n\n".join(sections)


async def fetch_marketplace_servers() -> list[dict]:
    """Fetch featured MCP servers from the marketplace."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(f"{DEDALUS_SITE_URL}/api/marketplace")
            if resp.status_code == 200:
                data = resp.json()
                repos = data.get("repositories", [])
                return [r for r in repos if r.get("tags", {}).get("use_cases", {}).get("featured", False)]
    except Exception:
        pass
    return []
