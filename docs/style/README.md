# Python Style

Python's philosophy—"There should be one obvious way to do it"—guides how we write code at Dedalus. This guide codifies our conventions for Wingman.

We're heavily inspired by [Google's Python style guide](https://google.github.io/styleguide/pyguide.html), adapted for our needs.

## The Documents

| Document                            | What It Covers                                | Who It's For                    |
| ----------------------------------- | --------------------------------------------- | ------------------------------- |
| [Guide](guide.md)                   | The foundations—formatting, naming, structure | Everyone                        |
| [Best Practices](best-practices.md) | Patterns that work well in practice           | Anyone who wants to level up    |
| [Reference](reference.md)           | Complete style reference with rationale       | Deep dives, understanding "why" |

**Guide** is definitive. If you read nothing else, read that.

**Best Practices** collects patterns that have proven useful. Not mandatory, but worth adopting.

**Reference** provides the complete style guide with full rationale (Definition → Pros → Cons → Decision) behind each choice.

## Why Bother

Style guides get a bad reputation. They can feel pedantic. But consider: every minute spent debating formatting is a minute not spent building something useful.

Python already solved most style debates with tools like `ruff`. These docs handle the rest.

The goal isn't uniformity for its own sake. It's **readability**. Code is read far more than it's written. Consistent style means readers spend their mental energy understanding logic, not deciphering formatting quirks.

## What These Docs Do

- Establish shared vocabulary for code reviews
- Document Python idioms with concrete examples
- Explain tradeoffs when multiple approaches work
- Reduce surprises during review

## What These Docs Don't Do

- List every possible comment a reviewer could make
- Replace judgment with rules
- Justify rewriting working code for style points

There will always be differences between programmers. That's fine. We're not aiming for perfect uniformity—we're aiming for code that's easy to read and maintain.

## Key Principles

### Clarity

The code's purpose should be obvious to readers:

- Use descriptive variable names
- Add comments that explain _why_, not _what_
- Break up dense code with whitespace
- Extract complex logic into well-named functions

### Simplicity

Write code for the people who will use, read, and maintain it:

- Don't add unnecessary abstraction
- Prefer stdlib over external dependencies
- Use mundane names for mundane things
- Avoid "clever" code

### Consistency

Match the patterns already in the codebase:

- Use the same naming conventions
- Follow existing module structure
- Match error handling patterns

## Tooling

We use modern Python tooling—fast, Rust-based tools that have become the industry standard.

### Project Management: uv

[uv](https://docs.astral.sh/uv/) is an extremely fast Python package and project manager. It replaces `pip`, `pip-tools`, `pipx`, `poetry`, `pyenv`, and `virtualenv` with a single tool that's 10-100x faster.

```bash
uv sync              # Install dependencies from lockfile
uv add httpx         # Add a dependency
uv run pytest        # Run commands in the virtual environment
uv python install    # Install Python versions
```

### Linting & Formatting: ruff

[ruff](https://docs.astral.sh/ruff/) is an extremely fast Python linter and formatter. It replaces Flake8, Black, isort, and dozens of Flake8 plugins with a single tool that's 10-100x faster.

```bash
uv run ruff check src/wingman/       # Find issues
uv run ruff check src/wingman/ --fix # Auto-fix what can be fixed
uv run ruff format src/wingman/      # Format code (replaces Black)
```

Ruff provides 800+ built-in rules with native re-implementations of popular plugins. It catches issues instantly—no more waiting for slow linters.

### Type Checking: mypy → ty

[mypy](https://mypy.readthedocs.io/) is currently our static type checker. It catches type errors at development time rather than runtime.

```bash
uv run mypy src/wingman
```

**Future: ty.** We're watching [ty](https://github.com/astral-sh/ty), Astral's Rust-based type checker. It completes our all-Astral toolchain (uv + ruff + ty) and promises the same 10-100x speed improvements. We'll adopt ty at beta and drop mypy at GA.

### All Together

```bash
# Full check before commit
uv run ruff check src/wingman/ --fix
uv run ruff format src/wingman/
uv run mypy src/wingman
uv run pytest
```

All code must pass these checks before merge.

## Quick Reference

### Naming

| Type     | Convention            | Example           |
| -------- | --------------------- | ----------------- |
| Module   | `snake_case`          | `sessions.py`     |
| Class    | `PascalCase`          | `WingmanApp`      |
| Function | `snake_case`          | `get_session()`   |
| Constant | `SCREAMING_SNAKE`     | `DEFAULT_TIMEOUT` |
| Private  | `_leading_underscore` | `_internal_state` |

### Imports

```python
# Standard library
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

# Third-party
from pydantic import BaseModel

# Local
from wingman.sessions import get_session
```

### Type Hints

Required for all public APIs:

```python
def process_tool(
    name: str,
    handler: Callable[..., Any],
    *,
    description: str | None = None,
) -> Tool:
    """Process and register a tool handler."""
    ...
```

### Docstrings

Google style, always for public APIs:

```python
def fetch_resource(uri: str, *, timeout: float = 30.0) -> Resource:
    """Fetch a resource by URI.

    Args:
        uri: The resource URI to fetch.
        timeout: Request timeout in seconds.

    Returns:
        The fetched resource.

    Raises:
        ResourceNotFoundError: If the resource doesn't exist.
        TimeoutError: If the request times out.
    """
```

## Further Reading

**Python Fundamentals**

- [PEP 8](https://peps.python.org/pep-0008/) — Style Guide for Python Code
- [PEP 257](https://peps.python.org/pep-0257/) — Docstring Conventions
- [PEP 484](https://peps.python.org/pep-0484/) — Type Hints

**Type Hints**

- [typing module docs](https://docs.python.org/3/library/typing.html)
- [Pydantic documentation](https://docs.pydantic.dev/)

**Tooling**

- [uv documentation](https://docs.astral.sh/uv/) — Project management
- [ruff documentation](https://docs.astral.sh/ruff/) — Linting and formatting
- [mypy documentation](https://mypy.readthedocs.io/) — Type checking

## Next Steps

Start with the [Guide](guide.md). It covers formatting, naming, and structure—the fundamentals you'll use every day.
