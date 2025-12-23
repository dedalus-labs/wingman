# Guidelines For Coding Agents

Instructions for AI coding agents (Claude, Codex, Cursor, Devin, etc.) working on this codebase.

## Essential Commands

```bash
# Install dependencies
uv sync --extra dev

# Run the app
uv run wingman

# Test
uv run pytest

# Lint and format
uv run ruff check src/wingman/
uv run ruff format src/wingman/
```

## Before You Code

**Scan wide before you write.** Search for logic that already does what you need. Understand where your contribution fits contextually within this codebase.

1. Grep the codebase for related functionality—it may already exist
2. Look at similar existing code for patterns and conventions
3. Identify code that your implementation should integrate with

## Code Standards

- All code formatted with `ruff format` (double quotes)
- Type hints required for function signatures
- Google-style docstrings for public APIs
- Follow existing patterns in `src/wingman/app.py` and `src/wingman/ui/`

**Style Guides**: For comprehensive Python style conventions, see [`docs/style/`](docs/style/):

- [Guide](docs/style/guide.md) — Formatting, naming, structure (start here)
- [Best Practices](docs/style/best-practices.md) — Patterns that work well
- [Reference](docs/style/reference.md) — Complete style reference with rationale

### Naming

| Type     | Convention        | Example           |
| -------- | ----------------- | ----------------- |
| Module   | `snake_case`      | `sessions.py`     |
| Class    | `PascalCase`      | `WingmanApp`      |
| Function | `snake_case`      | `get_session()`   |
| Constant | `SCREAMING_SNAKE` | `DEFAULT_MODELS`  |
| Private  | `_leading_under`  | `_internal_state` |

## Key Files

| Path                      | Purpose                     |
| ------------------------- | --------------------------- |
| `src/wingman/app.py`      | Main Textual application    |
| `src/wingman/config.py`   | Configuration and constants |
| `src/wingman/ui/`         | TUI widgets and modals      |
| `src/wingman/tools.py`    | Tool definitions for agents |
| `src/wingman/sessions.py` | Chat session management     |

## Don't

- Add dependencies without justification
- Modify the Dedalus API client directly
- Commit API keys or credentials
- Break the TUI layout without testing
- Use `panic()`-style exceptions for recoverable errors

## Do

- Run the app locally before suggesting UI changes
- Test on multiple terminal sizes
- Follow Textual best practices for reactive UI
- Fail explicitly rather than silently degrade
- Ask clarifying questions if requirements are ambiguous
