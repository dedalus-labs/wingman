"""Configuration and constants."""

import json
from pathlib import Path

import httpx

# Paths
CONFIG_DIR = Path.home() / ".wingman"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"
CHECKPOINTS_DIR = CONFIG_DIR / "checkpoints"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# App metadata
APP_NAME = "Wingman"
APP_VERSION = "0.1.0"
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
]


def load_api_key() -> str | None:
    """Load API key from config file."""
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
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
            config = json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    config["api_key"] = api_key
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


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
