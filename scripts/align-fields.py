#!/usr/bin/env python3
"""Column-align dataclass and enum fields inside ``# fmt: off`` blocks.

Scans Python files for ``# fmt: off`` / ``# fmt: on`` regions and
pads field names, type annotations, defaults, and inline comments
into aligned columns.

Usage::

    scripts/align-fields.py                       # fix all src/ files
    scripts/align-fields.py --check               # exit 1 if misaligned
    scripts/align-fields.py src/wingman/tools.py  # fix specific files

"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

MIN_GAP = 2

SKIP_PREFIXES = ("#", "def ", "@", "class ", '"""', "'''", ")", "]", "}")


# --- Data types ---


@dataclass(frozen=True, slots=True)
class Field:
    """Parsed representation of one field line.

    Covers both typed fields (``name: type = default``) and bare
    assignments (``NAME = value``).

    """

    # fmt: off
    indent:    str
    name:      str
    type_ann:  str
    default:   str
    comment:   str
    has_colon: bool
    # fmt: on


# --- Parsing ---


def is_field_line(line: str) -> bool:
    """Test whether a line looks like a dataclass field or enum member.

    Returns:
        True if the line contains ``:`` or ``=`` and is not a comment,
        decorator, class def, or continuation bracket.

    """
    stripped = line.strip()
    if not stripped:
        return False
    if any(stripped.startswith(p) for p in SKIP_PREFIXES):
        return False
    return ":" in stripped or "=" in stripped


def find_top_level(s: str, target: str) -> int | None:
    """Find the first occurrence of ``target`` outside strings and brackets.

    Args:
        s: Source string to scan.
        target: Single character to find.

    Returns:
        Index of the first top-level occurrence, or None.

    """
    depth = 0
    in_str = False
    str_char = ""
    for i, ch in enumerate(s):
        if in_str:
            if ch == str_char and (i == 0 or s[i - 1] != "\\"):
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            str_char = ch
        elif ch in ("(", "[", "{"):
            depth += 1
        elif ch in (")", "]", "}"):
            depth -= 1
        elif ch == target and depth == 0:
            if target == "=":
                if i + 1 < len(s) and s[i + 1] == "=":
                    continue
                if i > 0 and s[i - 1] in ("!", "<", ">"):
                    continue
            return i
    return None


def split_comment(text: str) -> tuple[str, str]:
    """Separate trailing inline comment from code.

    Args:
        text: Stripped line content (no leading whitespace).

    Returns:
        (code, comment) where comment includes the ``#``.

    """
    idx = find_top_level(text, "#")
    if idx is None:
        return text, ""
    return text[:idx].rstrip(), text[idx:]


def parse_field(line: str) -> Field | None:
    """Parse a single line into a Field, or None if not a field.

    Args:
        line: Raw source line (may include trailing newline).

    Returns:
        Parsed Field or None if the line is not a field.

    """
    if not is_field_line(line):
        return None

    indent = line[: len(line) - len(line.lstrip())]
    stripped = line.strip()
    code, comment = split_comment(stripped)

    if ":" in code:
        colon = code.index(":")
        name = code[:colon].strip()
        rest = code[colon + 1 :].strip()

        eq = find_top_level(rest, "=")
        if eq is not None:
            type_ann = rest[:eq].strip()
            default = rest[eq + 1 :].strip()
        else:
            type_ann = rest
            default = ""

        return Field(indent, name, type_ann, default, comment, has_colon=True)

    eq = find_top_level(code, "=")
    if eq is None:
        return None
    name = code[:eq].strip()
    default = code[eq + 1 :].strip()
    return Field(indent, name, "", default, comment, has_colon=False)


# --- Alignment ---


def align_block(lines: list[str]) -> list[str]:
    """Column-align a group of lines from a ``# fmt: off`` block.

    Non-field lines (blank lines, class defs, decorators) pass through
    unchanged. Field lines get padded so names, types, defaults, and
    comments form clean columns.

    Args:
        lines: Source lines between ``# fmt: off`` and ``# fmt: on``.

    Returns:
        Aligned lines (same length as input).

    """
    parsed = [parse_field(line) for line in lines]
    fields = [f for f in parsed if f is not None]

    if len(fields) < 2:
        return lines

    has_types = any(f.has_colon for f in fields)
    has_defaults = any(f.default for f in fields)
    has_comments = any(f.comment for f in fields)

    if has_types:
        max_name_col = max(len(f.name) + 1 for f in fields if f.has_colon)
    else:
        max_name_col = max(len(f.name) for f in fields)
    max_type = max((len(f.type_ann) for f in fields if f.type_ann), default=0)

    result = []
    for line, field in zip(lines, parsed):
        if field is None:
            result.append(line)
            continue

        parts = [field.indent]

        if has_types and field.has_colon:
            parts.append((field.name + ":").ljust(max_name_col))
            parts.append(" ")
            parts.append(field.type_ann.ljust(max_type) if field.type_ann else " " * max_type)
        elif has_types:
            parts.append(field.name.ljust(max_name_col))
            parts.append(" " * (max_type + 1))
        else:
            parts.append(field.name.ljust(max_name_col))

        if has_defaults and field.default:
            parts.append(" " * MIN_GAP + "= " + field.default)

        if has_comments and field.comment:
            so_far = "".join(parts).rstrip()
            parts = [so_far, " " * MIN_GAP + " " + field.comment]

        rebuilt = "".join(parts).rstrip()
        nl = "\n" if line.endswith("\n") else ""
        result.append(rebuilt + nl)

    return result


# --- File processing ---


def process_file(path: Path, *, check: bool = False) -> bool:
    """Align all ``# fmt: off`` blocks in a single file.

    Args:
        path: Python source file to process.
        check: If True, report misalignment without modifying the file.

    Returns:
        True if the file is already aligned (or was successfully fixed).

    """
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    new_lines = list(lines)
    changed = False

    i = 0
    block_start = -1
    in_block = False

    while i < len(lines):
        stripped = lines[i].strip()

        if stripped == "# fmt: off":
            in_block = True
            block_start = i + 1
        elif stripped == "# fmt: on" and in_block:
            in_block = False
            block = lines[block_start:i]
            aligned = align_block(block)
            if aligned != block:
                changed = True
                new_lines[block_start:i] = aligned
        i += 1

    if not changed:
        return True
    if check:
        return False

    path.write_text("".join(new_lines))
    return True


def collect_paths(args: list[str]) -> list[Path]:
    """Resolve CLI arguments into a sorted list of Python file paths.

    Args:
        args: File or directory paths from the command line.

    Returns:
        Sorted list of ``.py`` file paths.

    Raises:
        SystemExit: If a path does not exist.

    """
    paths: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            paths.extend(p.rglob("*.py"))
        elif p.is_file():
            paths.append(p)
        else:
            print(f"Not found: {arg}", file=sys.stderr)
            raise SystemExit(1)
    return sorted(paths)


def main() -> int:
    """Entry point for the align-fields formatter.

    Returns:
        0 on success, 1 if misaligned files found in check mode.

    """
    argv = sys.argv[1:]
    check = "--check" in argv
    args = [a for a in argv if a != "--check"] or ["src/"]

    paths = collect_paths(args)
    misaligned = [p for p in paths if not process_file(p, check=check)]

    if check and misaligned:
        for p in misaligned:
            print(f"MISALIGNED: {p}")
        print("\nRun: python scripts/align-fields.py")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
