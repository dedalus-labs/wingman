"""Configuration and constants."""

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


# Models
DEFAULT_MODELS = [
    # OpenAI
    "openai/gpt-5",
    "openai/gpt-5-mini",
    "openai/gpt-4.1",
    "openai/gpt-4.1-mini",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/o1",
    "openai/o3",
    "openai/o3-mini",
    "openai/o4-mini",
    "openai/gpt-4-turbo",
    # Anthropic
    "anthropic/claude-opus-4-5-20251101",
    "anthropic/claude-sonnet-4-5-20250929",
    "anthropic/claude-haiku-4-5-20251001",
    "anthropic/claude-sonnet-4-20250514",
    # Google
    "google/gemini-2.5-pro",
    "google/gemini-2.5-flash",
    "google/gemini-2.0-flash",
    # xAI
    "xai/grok-4-fast-reasoning",
    "xai/grok-4-fast-non-reasoning",
    "xai/grok-3",
    "xai/grok-3-mini",
    # DeepSeek
    "deepseek/deepseek-chat",
    "deepseek/deepseek-reasoner",
    # Mistral
    "mistral/mistral-large-latest",
    "mistral/mistral-small-latest",
    "mistral/codestral-2508",
]

MODELS: list[str] = DEFAULT_MODELS.copy()
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
    ("/key", "API key"),
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
    "mcp": ["clear", "list", "remove"],
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


def save_api_key(api_key: str) -> None:
    """Save API key to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {}
    if CONFIG_FILE.exists():
        try:
            config = oj.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    config["api_key"] = api_key
    CONFIG_FILE.write_text(oj.dumps(config, indent=2))


INSTRUCTION_FILENAMES = ["AGENTS.md", "WINGMAN.md"]
MAX_INSTRUCTION_BYTES = 32 * 1024  # 32KB limit per file


def load_instructions(working_dir: Path | None = None) -> str:
    """Load instructions from ~/.wingman/AGENTS.md (global) and .wingman/AGENTS.md (local).

    Returns combined instructions with hierarchy framing, or empty string if none found.
    Global instructions take precedence; local instructions provide project context.
    """
    global_content: str | None = None
    local_content: str | None = None

    # Global instructions (~/.wingman/AGENTS.md) - higher priority, user-level defaults
    for name in INSTRUCTION_FILENAMES:
        global_path = CONFIG_DIR / name
        try:
            if global_path.is_file():
                content = global_path.read_text("utf-8", errors="ignore")[:MAX_INSTRUCTION_BYTES]
                if content.strip():
                    global_content = content.strip()
                break
        except (OSError, IOError):
            continue

    # Local instructions - AGENTS.md in working directory (project root)
    if working_dir:
        for name in INSTRUCTION_FILENAMES:
            local_path = working_dir / name
            try:
                if local_path.is_file():
                    content = local_path.read_text("utf-8", errors="ignore")[:MAX_INSTRUCTION_BYTES]
                    if content.strip():
                        local_content = content.strip()
                    break
            except (OSError, IOError):
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
    """Fetch MCP servers from the marketplace."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(f"{DEDALUS_SITE_URL}/api/marketplace")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("repositories", [])
    except Exception:
        pass
    return []
