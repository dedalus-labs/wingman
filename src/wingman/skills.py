"""Skill loading and execution for wingman.

Loads SKILL.md files from ``.agents/skills/`` (source of truth) and
``.wingman/skills/`` (fallback), parses frontmatter metadata, and
expands skill prompts with argument substitution and shell execution.

"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .app import WingmanApp

SKILL_DIRS = [".agents/skills", ".wingman/skills"]
SKILL_FILE = "SKILL.md"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
SHELL_INLINE_RE = re.compile(r"!\`([^`]+)\`")


# fmt: off
@dataclass(frozen=True, slots=True)
class Skill:
    """Parsed skill definition from a SKILL.md file.

    """

    name:                 str
    description:          str
    content:              str
    path:                 Path
    allowed_tools:        list[str]   = field(default_factory=list)
    argument_hint:        str | None  = None
    user_invocable:       bool        = True
    disable_model_invoke: bool        = False
# fmt: on


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split SKILL.md into frontmatter dict and markdown body.

    Args:
        text: Raw file contents.

    Returns:
        (frontmatter_dict, markdown_body) tuple.

    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw_yaml = match.group(1)
    body = text[match.end() :]
    try:
        meta = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, body


def parse_allowed_tools(value: str | list | None) -> list[str]:
    """Normalize allowed-tools to a list of strings.

    Args:
        value: Frontmatter value — string (comma-separated) or list.

    Returns:
        List of tool name strings.

    """
    if not value:
        return []
    if isinstance(value, list):
        return [str(t).strip() for t in value]
    return [t.strip() for t in str(value).split(",")]


def load_skill(skill_dir: Path) -> Skill | None:
    """Load a single skill from a directory containing SKILL.md.

    Args:
        skill_dir: Path to the skill directory.

    Returns:
        Parsed Skill or None if SKILL.md is missing/invalid.

    """
    skill_file = skill_dir / SKILL_FILE
    if not skill_file.is_file():
        return None

    text = skill_file.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    name = meta.get("name", skill_dir.name)
    description = meta.get("description", "")
    if isinstance(description, str):
        description = " ".join(description.split())

    return Skill(
        name=name,
        description=description,
        content=body,
        path=skill_dir,
        allowed_tools=parse_allowed_tools(meta.get("allowed-tools")),
        argument_hint=meta.get("argument-hint"),
        user_invocable=meta.get("user-invocable", True) is not False,
        disable_model_invoke=meta.get("disable-model-invocation", False) is True,
    )


def discover_skills(cwd: Path) -> dict[str, Skill]:
    """Discover all skills from standard directories.

    Searches ``.agents/skills/`` first (source of truth), then
    ``.wingman/skills/`` as fallback. First occurrence of a skill
    name wins.

    Args:
        cwd: Working directory to resolve relative skill paths from.

    Returns:
        Dict mapping skill name to Skill.

    """
    skills: dict[str, Skill] = {}
    for rel_dir in SKILL_DIRS:
        base = cwd / rel_dir
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            skill = load_skill(entry)
            if skill and skill.name not in skills:
                skills[skill.name] = skill
    return skills


def substitute_arguments(content: str, args: str) -> str:
    """Replace ``$ARGUMENTS`` and positional ``$0``, ``$1`` placeholders.

    Args:
        content: Skill markdown body.
        args: Raw argument string from the user.

    Returns:
        Content with placeholders replaced.

    """
    if not args:
        return content

    result = content.replace("$ARGUMENTS", args)

    parts = args.split()
    for i, part in enumerate(parts):
        result = result.replace(f"${i}", part)

    if "$ARGUMENTS" not in content and "$0" not in content:
        result += f"\n\n## Arguments\n\n{args}"

    return result


def execute_shell_commands(content: str) -> str:
    """Execute inline ``!`command``` blocks and replace with output.

    Args:
        content: Skill markdown with shell commands.

    Returns:
        Content with command outputs inlined.

    """

    def run_command(match: re.Match) -> str:
        cmd = match.group(1)
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            output = result.stdout.strip() or result.stderr.strip()
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "(command timed out)"
        except Exception as e:
            return f"(error: {e})"

    return SHELL_INLINE_RE.sub(run_command, content)


def expand_skill(skill: Skill, args: str = "") -> str:
    """Build the full prompt for a skill invocation.

    Reads SKILL.md, substitutes arguments, executes shell commands,
    and prepends the skill directory path for file references.

    Args:
        skill: Parsed skill definition.
        args: User-provided arguments.

    Returns:
        Fully expanded prompt string.

    """
    content = skill.content
    content = substitute_arguments(content, args)
    content = execute_shell_commands(content)

    header = f"Skill: {skill.name}"
    if skill.path.is_dir():
        header += f"\nBase directory: {skill.path}"

    return f"{header}\n\n{content}"


class SkillManager:
    """Loads, caches, and executes skills.

    Attached to the app as ``self.skills``.

    """

    def __init__(self, app: WingmanApp) -> None:
        self.app = app
        self.registry: dict[str, Skill] = {}

    def load(self, cwd: Path | None = None) -> None:
        """Load skills from the working directory.

        Args:
            cwd: Directory to search for skills. Defaults to app's
                 active panel working dir or process cwd.

        """
        if cwd is None:
            panel = self.app.active_panel
            cwd = panel.working_dir if panel else Path.cwd()
        self.registry = discover_skills(cwd)

    def list_skills(self) -> list[Skill]:
        """Return all loaded user-invocable skills.

        Returns:
            List of skills where user_invocable is True.

        """
        return [s for s in self.registry.values() if s.user_invocable]

    def get(self, name: str) -> Skill | None:
        """Look up a skill by name.

        Args:
            name: Skill name (e.g., "commit", "pr").

        Returns:
            Skill or None.

        """
        return self.registry.get(name)

    def invoke(self, name: str, args: str = "") -> str | None:
        """Expand a skill and return its prompt.

        Args:
            name: Skill name.
            args: User arguments.

        Returns:
            Expanded prompt string, or None if skill not found.

        """
        skill = self.get(name)
        if not skill:
            return None
        return expand_skill(skill, args)

    def get_command_names(self) -> list[str]:
        """Return skill names for slash-command registration.

        Returns:
            List of skill names that are user-invocable.

        """
        return [s.name for s in self.list_skills()]
