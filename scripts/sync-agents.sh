#!/usr/bin/env bash
# Mirror skills from .agents/skills/ into .wingman/skills/.
#
# .agents/skills/ is the agent-neutral source of truth. Agent-specific
# tools (Claude Code, Codex, etc.) can read .wingman/skills/ as a
# fallback. Agent-only skills (those with no .agents/ counterpart)
# are left untouched.
#
# Usage:
#   scripts/sync-agents.sh           # sync in place
#   scripts/sync-agents.sh --check   # exit 1 if .wingman/ is out of sync

set -euo pipefail

mode="sync"
if [[ "${1:-}" == "--check" ]]; then
  mode="check"
fi

repo_root="$(git rev-parse --show-toplevel)"
src="$repo_root/.agents/skills"
dst="$repo_root/.wingman/skills"

if [[ ! -d "$src" ]]; then
  echo "sync-agents: $src does not exist, nothing to sync"
  exit 0
fi

drift=0
for skill_dir in "$src"/*/; do
  [[ -d "$skill_dir" ]] || continue
  name="$(basename "$skill_dir")"
  target="$dst/$name"

  if [[ "$mode" == "check" ]]; then
    if ! diff -rq "$skill_dir" "$target" >/dev/null 2>&1; then
      echo "DRIFT: .wingman/skills/$name is out of sync with .agents/skills/$name"
      drift=1
    fi
  else
    mkdir -p "$dst"
    rm -rf "$target"
    cp -R "$skill_dir" "$target"
  fi
done

if [[ "$mode" == "check" && "$drift" -eq 1 ]]; then
  echo
  echo "Run: scripts/sync-agents.sh"
  echo "Then commit the .wingman/skills/ changes."
  exit 1
fi
