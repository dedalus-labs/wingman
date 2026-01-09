"""Command input completion helpers for slash commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .config import COMMANDS, COMMAND_OPTIONS


@dataclass(frozen=True)
class CompletionResult:
    """Result of applying a completion to the input."""

    value: str
    cursor_position: int


@dataclass(frozen=True)
class CompletionRequest:
    """Request passed to dynamic completion providers."""

    value: str
    cursor_position: int
    command: str
    args: list[str]
    active_index: int
    active_text: str


CandidateProvider = Callable[[CompletionRequest], list[str] | None]


@dataclass(frozen=True)
class CompletionContext:
    """Resolved completion context for the current cursor position."""

    value: str
    cursor_position: int
    candidates: list[str]
    prefix: str
    replace_start: int
    replace_end: int
    include_slash: bool
    kind: str


@dataclass(frozen=True)
class _TokenSpan:
    """Token with its span in the input string."""

    text: str
    start: int
    end: int


def complete_command_input(
    value: str,
    cursor_position: int,
    candidate_provider: CandidateProvider | None = None,
) -> CompletionResult | None:
    """Apply tab completion for slash commands and their first-arg options.

    Args:
        value: Current input value.
        cursor_position: Cursor position in the input.
        candidate_provider: Optional provider for dynamic candidates.

    Returns:
        CompletionResult if a completion was applied, otherwise None.
    """
    context = get_completion_context(value, cursor_position, candidate_provider)
    if context is None or not context.candidates:
        return None

    completion = resolve_completion(context.prefix, context.candidates)
    if completion is None:
        return None
    add_space = len(context.candidates) == 1
    return apply_completion(context, completion, add_space)


def get_completion_context(
    value: str,
    cursor_position: int,
    candidate_provider: CandidateProvider | None = None,
) -> CompletionContext | None:
    """Get completion context for the current input and cursor."""
    parsed = _parse_context(value, cursor_position)
    if parsed is None:
        return None

    if parsed.active_index == 0:
        prefix = parsed.active.text[1:] if parsed.active.text.startswith("/") else parsed.active.text
        candidates = _match_commands(prefix)
        kind = "command"
        include_slash = True
    elif parsed.active_index == 1:
        options = COMMAND_OPTIONS.get(parsed.command)
        if not options:
            return None
        prefix = parsed.active.text
        candidates = _match_options(prefix, options)
        kind = "option"
        include_slash = False
    else:
        candidates = _get_dynamic_matches(parsed, value, cursor_position, candidate_provider)
        if not candidates:
            return None
        prefix = parsed.active.text
        kind = "argument"
        include_slash = False

    return CompletionContext(
        value=value,
        cursor_position=cursor_position,
        candidates=candidates,
        prefix=prefix,
        replace_start=parsed.active.start,
        replace_end=parsed.active.end,
        include_slash=include_slash,
        kind=kind,
    )


def get_hint_candidates(
    value: str,
    cursor_position: int | None = None,
    candidate_provider: CandidateProvider | None = None,
) -> list[str]:
    """Get command or option hint candidates for the current input.

    Args:
        value: Current input value.
        cursor_position: Optional cursor position, defaults to end of input.
        candidate_provider: Optional provider for dynamic candidates.

    Returns:
        List of candidate strings for display.
    """
    if cursor_position is None:
        cursor_position = len(value)
    context = _parse_context(value, cursor_position)
    if context is None:
        return []

    if context.active_index == 0:
        search = context.active.text[1:] if context.active.text.startswith("/") else context.active.text
        search_lower = search.lower()
        matches = [
            cmd
            for cmd, desc in COMMANDS
            if search_lower in cmd.lower() or search_lower in desc.lower()
        ]
        if len(matches) == 1 and matches[0].lstrip("/") == search:
            return []
        return matches

    if context.active_index == 1:
        options = COMMAND_OPTIONS.get(context.command)
        if not options:
            return []
        prefix = context.active.text
        matches = _match_options(prefix, options)
        if len(matches) == 1 and matches[0] == prefix:
            return []
        return matches

    dynamic = _get_dynamic_matches(context, value, cursor_position, candidate_provider)
    if dynamic:
        if len(dynamic) == 1 and dynamic[0] == context.active.text:
            return []
        return dynamic

    return []


@dataclass(frozen=True)
class _CompletionContext:
    value: str
    command: str
    tokens: list[_TokenSpan]
    active_index: int
    active: _TokenSpan


def _build_request(
    context: _CompletionContext,
    value: str,
    cursor_position: int,
) -> CompletionRequest:
    return CompletionRequest(
        value=value,
        cursor_position=cursor_position,
        command=context.command,
        args=[token.text for token in context.tokens[1:]],
        active_index=context.active_index,
        active_text=context.active.text,
    )


def _get_dynamic_matches(
    context: _CompletionContext,
    value: str,
    cursor_position: int,
    candidate_provider: CandidateProvider | None,
) -> list[str]:
    if not candidate_provider:
        return []
    request = _build_request(context, value, cursor_position)
    candidates = candidate_provider(request)
    if not candidates:
        return []
    return _match_options(context.active.text, candidates)


def _parse_context(value: str, cursor_position: int) -> _CompletionContext | None:
    if not value.lstrip().startswith("/"):
        return None
    tokens = _split_tokens(value)
    if not tokens or not tokens[0].text.startswith("/"):
        return None

    cursor = max(0, min(cursor_position, len(value)))
    active_index, active = _find_active_token(tokens, cursor)
    command = tokens[0].text[1:]
    return _CompletionContext(
        value=value,
        command=command,
        tokens=tokens,
        active_index=active_index,
        active=active,
    )


def _split_tokens(value: str) -> list[_TokenSpan]:
    tokens: list[_TokenSpan] = []
    i = 0
    length = len(value)
    while i < length:
        if value[i].isspace():
            i += 1
            continue
        start = i
        while i < length and not value[i].isspace():
            i += 1
        tokens.append(_TokenSpan(text=value[start:i], start=start, end=i))
    return tokens


def _find_active_token(tokens: list[_TokenSpan], cursor_position: int) -> tuple[int, _TokenSpan]:
    for idx, token in enumerate(tokens):
        if token.start <= cursor_position <= token.end:
            return idx, token
        if cursor_position < token.start:
            empty = _TokenSpan(text="", start=cursor_position, end=cursor_position)
            return idx, empty
    empty = _TokenSpan(text="", start=cursor_position, end=cursor_position)
    return len(tokens), empty


def _match_commands(prefix: str) -> list[str]:
    prefix_lower = prefix.lower()
    return [cmd.lstrip("/") for cmd, _ in COMMANDS if cmd.lower().startswith(f"/{prefix_lower}")]


def _match_options(prefix: str, options: list[str]) -> list[str]:
    prefix_lower = prefix.lower()
    return [opt for opt in options if opt.lower().startswith(prefix_lower)]


def resolve_completion(prefix: str, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    common = longest_common_prefix(candidates)
    if common and len(common) > len(prefix):
        return common
    return None


def longest_common_prefix(values: list[str]) -> str:
    if not values:
        return ""
    lower_values = [v.lower() for v in values]
    prefix = lower_values[0]
    for value in lower_values[1:]:
        while prefix and not value.startswith(prefix):
            prefix = prefix[:-1]
        if not prefix:
            break
    if not prefix:
        return ""
    return values[0][: len(prefix)]


def apply_completion(context: CompletionContext, replacement: str, add_space: bool) -> CompletionResult:
    """Apply a replacement to the active token using the completion context."""
    text = f"/{replacement}" if context.include_slash else replacement
    new_value = f"{context.value[:context.replace_start]}{text}{context.value[context.replace_end:]}"
    cursor_position = context.replace_start + len(text)
    if add_space and cursor_position == len(new_value) and not new_value.endswith(" "):
        new_value = f"{new_value} "
        cursor_position += 1
    return CompletionResult(value=new_value, cursor_position=cursor_position)
