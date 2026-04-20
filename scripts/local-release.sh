#!/usr/bin/env bash
# Build a wheel from the current tree, tag it locally, and install it as a
# tool so you can test the exact binary that would ship.
#
# Usage:
#   scripts/local-release.sh              # build + install from HEAD
#   scripts/local-release.sh v0.5.0       # override version tag
#   scripts/local-release.sh --list       # list local dev tags
#   scripts/local-release.sh --switch TAG # install a previously built version
#
# Wheels are cached in dist/. Local tags use the dev/ prefix to avoid
# collision with release tags.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

RED='\033[0;31m'
GREEN='\033[0;32m'
DIM='\033[2m'
NC='\033[0m'

list_tags() {
  git tag -l 'dev/*' --sort=-version:refname
}

switch_to() {
  local tag="$1"
  if ! git rev-parse "$tag" >/dev/null 2>&1; then
    echo -e "${RED}Tag $tag not found.${NC}" >&2
    echo "Available:"
    list_tags
    exit 1
  fi

  local sha
  sha="$(git rev-parse "$tag")"
  local wheel
  wheel="$(find dist -name "wingman_cli-*.whl" -newer "$(git rev-parse --git-dir)/refs/tags/$tag" 2>/dev/null | head -1)"

  if [[ -z "$wheel" ]]; then
    echo "No cached wheel for $tag. Building from that commit..."
    git stash --include-untracked -q 2>/dev/null || true
    git checkout "$tag" --detach -q
    uv build -q
    wheel="$(ls -t dist/wingman_cli-*.whl | head -1)"
    git checkout - -q
    git stash pop -q 2>/dev/null || true
  fi

  uv tool install "$wheel" --force
  echo -e "${GREEN}Installed wingman from $tag${NC}"
  wingman --version
}

build_and_install() {
  local version_tag="${1:-}"

  if [[ -z "$version_tag" ]]; then
    local pyproject_version
    pyproject_version="$(python3 -c "
import re, pathlib
text = pathlib.Path('pyproject.toml').read_text()
m = re.search(r'version\s*=\s*\"([^\"]+)\"', text)
print(m.group(1) if m else 'unknown')
")"
    local short_sha
    short_sha="$(git rev-parse --short HEAD)"
    version_tag="dev/${pyproject_version}-${short_sha}"
  elif [[ "$version_tag" != dev/* ]]; then
    version_tag="dev/${version_tag#v}"
  fi

  echo -e "${DIM}Building...${NC}"
  uv build -q

  local wheel
  wheel="$(ls -t dist/wingman_cli-*.whl | head -1)"

  if [[ -z "$wheel" ]]; then
    echo -e "${RED}Build produced no wheel.${NC}" >&2
    exit 1
  fi

  git tag -f "$version_tag" HEAD >/dev/null 2>&1
  echo -e "${DIM}Tagged ${version_tag}${NC}"

  uv tool install "$wheel" --force
  echo -e "${GREEN}Installed wingman from $wheel${NC}"
  wingman --version
  echo
  echo -e "Switch back:  ${DIM}scripts/local-release.sh --switch dev/VERSION${NC}"
  echo -e "List builds:  ${DIM}scripts/local-release.sh --list${NC}"
  echo -e "Editable dev: ${DIM}scripts/dev.sh --install${NC}"
}

case "${1:-}" in
  --list)
    list_tags
    ;;
  --switch)
    if [[ -z "${2:-}" ]]; then
      echo "Usage: scripts/local-release.sh --switch TAG"
      echo "Available:"
      list_tags
      exit 1
    fi
    switch_to "$2"
    ;;
  *)
    build_and_install "${1:-}"
    ;;
esac
