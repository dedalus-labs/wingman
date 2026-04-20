# Development

Local development workflow for iterating on wingman.

## Setup

```bash
uv sync --extra dev
```

## Daily Workflow

### Editable install + run

```bash
scripts/dev.sh              # install editable + launch wingman
scripts/dev.sh --install    # install editable only (no launch)
scripts/dev.sh --check      # lint + format check + test
```

The editable install means code changes take effect immediately — no
reinstall needed between edits.

### Manual equivalent

```bash
uv tool install --editable . --force
wingman                     # run from anywhere
```

## Pre-check

```bash
uv run ruff check src/wingman/
uv run ruff format --check src/wingman/
uv run pytest -q
```

Or all at once:

```bash
scripts/dev.sh --check
```

## Local Release Testing

Test the exact binary that would ship — a built wheel, not an editable
install. Useful for verifying packaging, entry points, and version strings.

### Build and install from HEAD

```bash
scripts/local-release.sh
```

This builds a wheel, tags the current commit locally as
`dev/<version>-<short-sha>`, and installs it via `uv tool install`.

### Override the version tag

```bash
scripts/local-release.sh v0.5.0
```

### Switch between builds

```bash
scripts/local-release.sh --list              # show all local dev tags
scripts/local-release.sh --switch dev/0.4.3-abc1234   # install a previous build
```

Tags use the `dev/` prefix and stay local — they never touch the remote
or collide with release tags.

### Back to editable dev

```bash
scripts/dev.sh --install
```

## Version

```bash
wingman --version           # wingman 0.4.3
```

The version comes from `importlib.metadata` at runtime, which reads
from the installed package metadata. In editable mode it reflects
`pyproject.toml`; in a built wheel it reflects the version baked into
the wheel.

## Dev Mode

Set `WINGMAN_DEV=1` to enable development features:

```bash
export WINGMAN_DEV=1
wingman
```

Currently enables:
- **Local bulletin loading** — reads from `./bulletin/` instead of
  fetching from GitHub

You can also point to a specific directory:

```bash
export WINGMAN_BULLETIN_PATH=/path/to/bulletin
```

## Agent Skills

Skills live in `.agents/skills/` (source of truth). After editing,
sync the `.wingman/` fallback mirror:

```bash
scripts/sync-agents.sh
```

CI enforces the mirror is in sync via `.github/workflows/agents-sync-check.yml`.

## Scripts Reference

| Script | Purpose |
| --- | --- |
| `scripts/dev.sh` | Editable install, check, run |
| `scripts/local-release.sh` | Build wheel, tag, install, switch versions |
| `scripts/sync-agents.sh` | Mirror `.agents/skills/` to `.wingman/skills/` |
| `scripts/install.sh` | End-user one-line install via uv |
