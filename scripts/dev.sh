#!/usr/bin/env bash
# One-command dev setup: editable install + optional launch.
#
# Usage:
#   scripts/dev.sh           # install editable + run wingman
#   scripts/dev.sh --install # install editable only (no launch)
#   scripts/dev.sh --check   # lint + format check + test
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

case "${1:-run}" in
  --install)
    echo "Installing wingman in editable mode..."
    uv tool install --editable . --force
    echo "Done. Run 'wingman' from anywhere."
    ;;
  --check)
    echo "Running lint, format check, and tests..."
    uv run ruff check src/wingman/
    uv run ruff format --check src/wingman/
    uv run pytest -q
    echo "All checks passed."
    ;;
  run|"")
    uv tool install --editable . --force 2>/dev/null
    exec wingman
    ;;
  *)
    echo "Usage: scripts/dev.sh [--install|--check|run]"
    exit 1
    ;;
esac
