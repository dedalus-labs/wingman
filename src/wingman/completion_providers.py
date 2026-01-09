"""Dynamic completion providers for command input."""

from __future__ import annotations

from .command_completion import CandidateProvider, CompletionRequest


def mcp_remove_provider(mcp_servers: list[str]) -> CandidateProvider:
    """Provide MCP server name completion for `/mcp remove`."""

    def provider(request: CompletionRequest) -> list[str] | None:
        if request.command != "mcp":
            return None
        if not request.args or request.args[0] != "remove":
            return None
        if request.active_index < 2:
            return None
        return mcp_servers

    return provider
