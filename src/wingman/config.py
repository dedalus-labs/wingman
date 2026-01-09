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


# Models (verified in models.dev)
DEFAULT_MODELS = [
    # OpenAI Chat
    "openai/gpt-5.2",
    "openai/gpt-5.1",
    "openai/gpt-5",
    "openai/gpt-5-mini",
    "openai/gpt-5-nano",
    "openai/gpt-5-chat-latest",
    "openai/gpt-4.1",
    "openai/gpt-4.1-mini",
    "openai/gpt-4.1-nano",
    "openai/gpt-4o",
    "openai/gpt-4o-2024-05-13",
    "openai/gpt-4o-mini",
    "openai/gpt-4-turbo",
    "openai/gpt-4",
    "openai/gpt-3.5-turbo",
    # OpenAI Reasoning
    "openai/o1",
    "openai/o3",
    "openai/o3-mini",
    "openai/o4-mini",
    # Anthropic
    "anthropic/claude-opus-4-5",
    "anthropic/claude-haiku-4-5-20251001",
    "anthropic/claude-sonnet-4-5-20250929",
    "anthropic/claude-opus-4-1-20250805",
    "anthropic/claude-opus-4-20250514",
    "anthropic/claude-sonnet-4-20250514",
    "anthropic/claude-3-7-sonnet-20250219",
    "anthropic/claude-3-5-haiku-20241022",
    "anthropic/claude-3-haiku-20240307",
    # Google
    "google/gemini-3-pro-preview",
    "google/gemini-3-flash-preview",
    "google/gemini-2.5-pro",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.0-flash",
    "google/gemini-2.0-flash-lite",
    # xAI
    "xai/grok-4-1-fast-non-reasoning",
    "xai/grok-4-fast-non-reasoning",
    "xai/grok-code-fast-1",
    "xai/grok-3",
    "xai/grok-3-mini",
    "xai/grok-2-vision-1212",
    # DeepSeek
    "deepseek/deepseek-chat",
    "deepseek/deepseek-reasoner",
    # Mistral
    "mistral/mistral-large-latest",
    "mistral/mistral-medium-latest",
    "mistral/mistral-small-latest",
    "mistral/pixtral-12b",
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
        except (OSError, IOError):
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
