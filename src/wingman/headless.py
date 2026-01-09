"""Headless mode for Wingman - runs without TUI for scripting and benchmarks."""

import asyncio
import sys
from pathlib import Path

from dedalus_labs import AsyncDedalus, DedalusRunner

from .config import MODELS, load_api_key, load_instructions
from .tools import CODING_SYSTEM_PROMPT, create_tools_headless


async def run_headless(
    prompt: str,
    model: str | None = None,
    working_dir: Path | None = None,
    allowed_tools: list[str] | None = None,
    max_tokens: int = 16384,
    verbose: bool = False,
) -> int:
    """Run Wingman in headless mode.

    Args:
        prompt: The task/prompt to execute
        model: Model to use (defaults to first in MODELS list)
        working_dir: Working directory for file operations
        allowed_tools: List of allowed tool names (None = all tools)
        max_tokens: Max tokens for response
        verbose: Print verbose output

    Returns:
        Exit code (0 = success, 1 = error)
    """
    api_key = load_api_key()
    if not api_key:
        print("Error: No API key configured. Run wingman interactively first to set up.", file=sys.stderr)
        return 1

    if working_dir is None:
        working_dir = Path.cwd()

    if model is None:
        model = MODELS[0]

    try:
        client = AsyncDedalus(api_key=api_key)
        runner = DedalusRunner(client)

        # Build system prompt
        system_content = CODING_SYSTEM_PROMPT.format(cwd=working_dir)

        # Include custom instructions (global first, then local)
        instructions = load_instructions(working_dir)
        if instructions:
            system_content += f"\n\n{instructions}"

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]

        # Create tools for headless mode (auto-approve all operations)
        tools = create_tools_headless(working_dir)

        # Filter tools if allowed_tools specified
        if allowed_tools:
            allowed_set = set(t.lower() for t in allowed_tools)
            tools = [t for t in tools if t.__name__.lower() in allowed_set]

        kwargs = {
            "messages": messages,
            "model": model,
            "tools": tools,
            "stream": False,  # Non-streaming for reliable tool execution
            "max_tokens": max_tokens,
            "max_steps": 50,  # Allow multiple tool calls
        }

        if verbose:
            print(f"Model: {model}", file=sys.stderr)
            print(f"Working dir: {working_dir}", file=sys.stderr)
            print(f"Tools: {[t.__name__ for t in tools]}", file=sys.stderr)
            print("---", file=sys.stderr)

        # Run the agentic loop (non-streaming for reliable tool execution)
        result = await runner.run(**kwargs)

        # Extract and print the final response
        if result is None:
            if verbose:
                print("Task completed (no response content)", file=sys.stderr)
        elif hasattr(result, "choices") and result.choices:
            content = result.choices[0].message.content
            if content:
                print(content)
            elif verbose:
                print("Task completed (empty content)", file=sys.stderr)
        elif hasattr(result, "content"):
            print(result.content)
        elif verbose:
            print(f"Task completed (result type: {type(result).__name__})", file=sys.stderr)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
