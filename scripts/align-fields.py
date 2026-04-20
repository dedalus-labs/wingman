#!/usr/bin/env python3
"""Align dataclass/enum fields inside ``# fmt: off`` blocks.

Scans Python files for ``# fmt: off`` / ``# fmt: on`` regions and
column-aligns assignment lines so that field names, type annotations,
default values, and inline comments line up.

Usage:
    scripts/align-fields.py                    # fix all src/ files in place
    scripts/align-fields.py --check            # exit 1 if anything is misaligned
    scripts/align-fields.py src/wingman/tools.py  # fix specific files
    scripts/align-fields.py --check src/       # check a directory
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Matches lines like:  name: type = default  # comment
#   or:                 NAME = ("value", ...)
FIELD_RE = re.compile(
    r"^(?P<indent>\s+)"
    r"(?P<name>\w+)"
    r"(?P<colon>:\s*)?(?P<type>[^=#]+?)?"
    r"(?P<eq>\s*=\s*)?"
    r"(?P<default>.+?)?"
    r"(?P<comment>\s*#\s*.+)?"
    r"$"
)

MIN_GAP = 2


def _is_field_line(line: str) -> bool:
    """Heuristic: line is a dataclass field or enum member assignment."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("def "):
        return False
    if stripped.startswith("@") or stripped.startswith("class "):
        return False
    if stripped.startswith(("\"\"\"", "'''", ")", "]", "}")):
        return False
    # Must have either `: type` or `= value`
    return ":" in stripped or "=" in stripped


def _parse_field(line: str) -> dict | None:
    """Parse a field line into parts for alignment."""
    stripped = line.strip()
    if not _is_field_line(line):
        return None

    indent = line[: len(line) - len(line.lstrip())]

    # Split off trailing inline comment
    comment = ""
    in_str = False
    str_char = ""
    paren_depth = 0
    comment_start = -1
    for i, ch in enumerate(stripped):
        if in_str:
            if ch == str_char and (i == 0 or stripped[i - 1] != "\\"):
                in_str = False
        elif ch in ('"', "'"):
            in_str = True
            str_char = ch
        elif ch in ("(", "[", "{"):
            paren_depth += 1
        elif ch in (")", "]", "}"):
            paren_depth -= 1
        elif ch == "#" and paren_depth == 0:
            comment_start = i
            break

    if comment_start >= 0:
        comment = stripped[comment_start:]
        stripped = stripped[:comment_start].rstrip()

    # Parse name: type = default
    if ":" in stripped:
        colon_idx = stripped.index(":")
        name = stripped[:colon_idx].strip()
        rest = stripped[colon_idx + 1:].strip()

        if "=" in rest:
            # Find top-level `=` (not inside parens/brackets)
            eq_idx = _find_top_level_eq(rest)
            if eq_idx is not None:
                type_ann = rest[:eq_idx].strip()
                default = rest[eq_idx + 1:].strip()
            else:
                type_ann = rest
                default = ""
        else:
            type_ann = rest
            default = ""

        return {
            "indent": indent,
            "name": name,
            "type": type_ann,
            "default": default,
            "comment": comment,
            "has_colon": True,
        }

    elif "=" in stripped:
        eq_idx = _find_top_level_eq(stripped)
        if eq_idx is None:
            return None
        name = stripped[:eq_idx].strip()
        default = stripped[eq_idx + 1:].strip()
        return {
            "indent": indent,
            "name": name,
            "type": "",
            "default": default,
            "comment": comment,
            "has_colon": False,
        }

    return None


def _find_top_level_eq(s: str) -> int | None:
    """Find the first `=` not inside parens/brackets/strings."""
    depth = 0
    in_str = False
    str_char = ""
    for i, ch in enumerate(s):
        if in_str:
            if ch == str_char and (i == 0 or s[i - 1] != "\\"):
                in_str = False
        elif ch in ('"', "'"):
            in_str = True
            str_char = ch
        elif ch in ("(", "[", "{"):
            depth += 1
        elif ch in (")", "]", "}"):
            depth -= 1
        elif ch == "=" and depth == 0:
            # Skip == and !=
            if i + 1 < len(s) and s[i + 1] == "=":
                continue
            if i > 0 and s[i - 1] in ("!", "<", ">"):
                continue
            return i
    return None


def _align_block(lines: list[str]) -> list[str]:
    """Align a group of consecutive field lines."""
    parsed = []
    for line in lines:
        p = _parse_field(line)
        if p:
            parsed.append(p)
        else:
            parsed.append(None)

    fields = [p for p in parsed if p is not None]
    if len(fields) < 2:
        return lines

    has_types = any(f["has_colon"] for f in fields)
    has_defaults = any(f["default"] for f in fields)
    has_comments = any(f["comment"] for f in fields)

    # name+colon is one visual unit: "name:" then space then type
    if has_types:
        max_name_col = max(len(f["name"]) + 1 for f in fields if f["has_colon"])
    else:
        max_name_col = max(len(f["name"]) for f in fields)
    max_type = max((len(f["type"]) for f in fields if f["type"]), default=0)

    result = []
    for line, p in zip(lines, parsed):
        if p is None:
            result.append(line)
            continue

        parts = [p["indent"]]

        if has_types and p["has_colon"]:
            name_colon = p["name"] + ":"
            parts.append(name_colon.ljust(max_name_col))
            parts.append(" ")
            parts.append(p["type"].ljust(max_type) if p["type"] else " " * max_type)
        elif has_types and not p["has_colon"]:
            parts.append(p["name"].ljust(max_name_col))
            parts.append(" " * (max_type + 1))
        else:
            parts.append(p["name"].ljust(max_name_col))

        if has_defaults and p["default"]:
            parts.append(" " * MIN_GAP + "= " + p["default"])

        if has_comments and p["comment"]:
            so_far = "".join(parts).rstrip()
            parts = [so_far]
            parts.append(" " * MIN_GAP + " " + p["comment"])

        rebuilt = "".join(parts).rstrip()
        result.append(rebuilt + "\n" if line.endswith("\n") else rebuilt)

    return result


def process_file(path: Path, check: bool = False) -> bool:
    """Process one file. Returns True if file is aligned (or was fixed)."""
    text = path.read_text()
    lines = text.splitlines(keepends=True)

    in_fmt_off = False
    block_start = -1
    new_lines = list(lines)
    changed = False

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if stripped == "# fmt: off":
            in_fmt_off = True
            block_start = i + 1
            i += 1
            continue

        if stripped == "# fmt: on" and in_fmt_off:
            in_fmt_off = False
            block = lines[block_start:i]
            aligned = _align_block(block)
            if aligned != block:
                changed = True
                new_lines[block_start:i] = aligned
            i += 1
            continue

        i += 1

    if not changed:
        return True

    if check:
        return False

    path.write_text("".join(new_lines))
    return True


def main() -> int:
    args = sys.argv[1:]
    check = "--check" in args
    args = [a for a in args if a != "--check"]

    if not args:
        args = ["src/"]

    paths: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            paths.extend(p.rglob("*.py"))
        elif p.is_file():
            paths.append(p)
        else:
            print(f"Not found: {arg}", file=sys.stderr)
            return 1

    misaligned = []
    for path in sorted(paths):
        ok = process_file(path, check=check)
        if not ok:
            misaligned.append(path)

    if check and misaligned:
        for p in misaligned:
            print(f"MISALIGNED: {p}")
        print(f"\nRun: python scripts/align-fields.py")
        return 1

    if not check and misaligned:
        # This shouldn't happen (we fixed them), but just in case
        for p in misaligned:
            print(f"Fixed: {p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
