---
name: pr
description: Create a pull request using the wingman PR template. Injects git state, commit history, and diff stats automatically.
allowed-tools: Bash(git *), Bash(gh *), Bash(awk *), Bash(sort *), Read
argument-hint: "[base-branch] [--branch <source-branch>]"
---

## Context (auto-detected from HEAD)

- Current branch: !`git branch --show-current`
- Remote status: !`git status -sb | head -1`

## PR Template

Read `.github/PULL_REQUEST_TEMPLATE.md` and fill every section. The template is mandatory.
Do not free-form the PR body.

## Rules

- PR title: `type(scope): description` (conventional commit format, under 70 chars)
- Target branch: first positional arg from `$ARGUMENTS` if provided, otherwise `main`
- Source branch: if `--branch <name>` is in `$ARGUMENTS`, use that branch for diff/log
  commands instead of HEAD. This is needed when the PR branch lives in a different worktree
  or the main repo checkout.
- Push with `-u` if needed
- Use `gh pr create` with `--body "$(cat <<'EOF' ... EOF)"` for correct formatting
- LOC check: if diff exceeds 200 changed lines (excluding generated files), warn the user
  and suggest splitting into stacked PRs

## Task

1. Determine the source branch: use `--branch` value if provided, otherwise current HEAD
2. Gather context by running:
   - `git log --oneline origin/main..<source-branch>` (commits for this PR)
   - `git diff --stat origin/main..<source-branch>` (diff stats)
   - `git diff --name-only origin/main..<source-branch>` (changed files)
3. Push the branch if needed
4. Read the PR template
5. Create the PR with every template section filled
6. Return the PR URL
