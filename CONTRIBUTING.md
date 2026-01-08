# Contributing to Wingman

Thanks for your interest in contributing! This guide will help you get started.

## Your First Pull Request

Never made a PR before? Welcome! Here's how to contribute step-by-step.

### 1. Fork the repository

Click the **Fork** button on the [Wingman repo](https://github.com/dedalus-labs/wingman). This creates your own copy.

### 2. Clone your fork

```bash
git clone https://github.com/YOUR-USERNAME/wingman.git
cd wingman
```

### 3. Set up the project

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (including dev tools)
uv sync --extra dev
```

### 4. Create a branch

```bash
git checkout -b fix/my-first-contribution
```

Pick a name that describes your change: `fix/typo-in-readme`, `feat/add-keyboard-shortcut`, `docs/clarify-setup`.

### 5. Make your changes

Edit the code, then run the checks:

```bash
uv run ruff check src/wingman/   # Lint
uv run ruff format src/wingman/  # Format
uv run pytest                    # Test
uv run wingman                   # Test the TUI manually
```

### 6. Commit with a conventional message

```bash
git add .
git commit -m "fix: correct typo in error message"
```

The commit type (`fix:`, `feat:`, `docs:`) matters—it determines the version bump. See [conventional commits](docs/conventional-commits.md).

### 7. Push to your fork

```bash
git push origin fix/my-first-contribution
```

### 8. Open a Pull Request

Go to your fork on GitHub. You'll see a banner to **Compare & pull request**. Click it!

- **Base repository**: `dedalus-labs/wingman`, branch `main`
- **Head repository**: your fork, your branch
- Write a clear title (this becomes the commit message when we merge)
- Describe what you changed and why

### 9. Wait for review

CI will run automatically. A maintainer will review your PR and may suggest changes. Don't worry—this is normal and collaborative!

### 🎉 Congratulations!

Once merged, you're officially a contributor. Your name appears in the git history, and if your change is a `feat:` or `fix:`, it'll be in the next release changelog. Thank you!

---

## Trunk-Based Development

All development happens on `main`. There's no `dev` or `staging` branch—PRs go directly to `main`.

**Tips:**

- **Short-lived branches**: Aim to merge within days, not weeks. Long-lived branches accumulate merge conflicts.
- **Small PRs are better**: Easier to review, faster to merge, lower risk.
- **Work-in-progress is fine**: Use feature flags or don't expose unfinished work in the public API.
- **`main` is always shippable**: Don't merge broken code. If something slips through, we revert quickly.

## Code Standards

```bash
uv run ruff check src/wingman/       # Lint
uv run ruff format --check src/wingman/  # Format check
uv run pytest                        # Test
```

All must pass. See the [style guide](docs/style/README.md).

## Dev Mode

Set `WINGMAN_DEV=1` to enable development features:

```bash
export WINGMAN_DEV=1
uv run wingman
```

This enables:
- **Local bulletin loading**: Reads messages from `./bulletin/` instead of fetching from GitHub
- Useful for testing new banners, tips, or notices before committing

You can also set `WINGMAN_BULLETIN_PATH=/path/to/bulletin` to point to a specific directory.

## AI Disclosure

If you use AI tools (Copilot, Claude, Cursor), mention it in your PR. You must understand code you submit.

## Areas Needing Help

- **Documentation**: Improve README, add examples
- **Testing**: Increase coverage
- **UI/UX**: Improve TUI widgets and layout
- **Features**: New tools, model integrations

Look for issues labeled `good first issue` to get started.

## Links

| Resource | Description |
|----------|-------------|
| [Style Guide](docs/style/README.md) | Python conventions |
| [Conventional Commits](docs/conventional-commits.md) | Commit message format |
| [SECURITY.md](SECURITY.md) | Reporting vulnerabilities |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
