---
name: commit
description: Create a git commit with conventional commit format. Injects current git state automatically.
allowed-tools: Bash(git add *), Bash(git status *), Bash(git commit *), Bash(git diff *)
---

## Context

- Status: !`git status -sb`
- Diff: !`git diff HEAD --stat`
- Branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`

## Rules

Commits are terse one-liner conventional commits: `type(scope): description`.

- type: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- scope: affected area (module, package, or feature)
- description: imperative mood, lowercase, no period, under 72 characters
- Never use "and" in a commit message. Two changes = two commits.

Stage files by name (never `git add -A` or `git add .`). Group changes by intent.

## Task

Based on the context above, stage the relevant files and create the commit.
Do not use any other tools. Do not send any text besides the tool calls.
