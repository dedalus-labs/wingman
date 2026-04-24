---
name: promote
description: Create a changelog-style promotion PR between two branches. Use for release promotions or branch-to-branch merges with a structured changelog.
allowed-tools: Bash(git *), Bash(gh *), Read
argument-hint: "[--from <branch>] [--to <branch>] [--dry-run]"
---

## Context (auto-detected)

- Commits to promote: !`git log --oneline origin/main..HEAD 2>/dev/null || echo "(no commits ahead of main)"`

## Rules

- Default: promote current branch → `main`
- `--from <branch>` overrides source (default: current branch)
- `--to <branch>` overrides target (default: `main`)
- `--dry-run` prints the PR body without creating it
- Commits are grouped by conventional commit type into changelog sections

## Changelog Sections

| Prefix | Section |
|--------|---------|
| `feat` | Features |
| `fix` | Bug Fixes |
| `refactor` | Refactors |
| `perf` | Performance |
| `test` | Tests |
| `docs` | Documentation |
| `chore`, `ci` | Chores |

Unrecognized prefixes go under Chores.

## Task

1. Parse `$ARGUMENTS` for `--from`, `--to`, `--dry-run`
2. Fetch the latest from origin for both branches
3. Get the commit list: `git log --format="%H %s" origin/<to>..origin/<from>`
4. If no commits, report that target is up to date and stop
5. Build the changelog body:
   - Group commits by section using the table above
   - Each bullet: `* **scope:** description ([short-hash](commit-url))` or `* description ([short-hash](commit-url))` if unscoped
   - Include a "Full Changelog" comparison link
   - Order sections: Features, Bug Fixes, Refactors, Performance, Tests, Documentation, Chores
6. If `--dry-run`, print the body and stop
7. Create the PR via `gh pr create --base <to> --head <from> --title "chore(release): promote <from> → <to>" --body "..."`
8. Return the PR URL
