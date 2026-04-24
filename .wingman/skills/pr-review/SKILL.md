---
name: pr-review
description: Review PR comments from GitHub. Fetches inline review comments and issue comments, classifies by blocking vs non-blocking, and summarizes actionable items.
allowed-tools: Bash(gh *), Read, Grep, Glob, Agent
argument-hint: "<pr-number> [--repo owner/repo]"
---

# Review PR Comments

## Context

- Branch: !`git branch --show-current`
- Remote: !`gh repo view --json nameWithOwner -q .nameWithOwner`

## Task

Given PR number `$ARGUMENTS` (required), fetch and triage all reviewer comments.

### 1. Fetch comments

Run these two `gh api` calls to get both comment types:

```bash
# Inline review comments (attached to specific lines)
gh api repos/{owner}/{repo}/pulls/{pr}/comments --paginate

# Issue-level comments (general discussion)
gh api repos/{owner}/{repo}/issues/{pr}/comments --paginate
```

If `--repo` is provided in arguments, use that. Otherwise infer from the git remote.

Filter out bot comments (author login ending in `[bot]` or `bot`).

### 2. Parse and classify

For each human comment, extract:

- **Author**: `.user.login`
- **Type**: `review` (inline) or `discussion` (issue-level)
- **File + line**: `.path` and `.line` (review comments only)
- **Body**: `.body`
- **Blocking**: true if body contains `blocking:`, `must-fix:`, `bug:`, `security:`, or `tests:` prefix
- **Created**: `.created_at`

### 3. Summarize

Output a table grouped by blocking status:

```
## Blocking (must resolve before merge)

| # | Author | File:Line | Comment |
|---|--------|-----------|---------|
| 1 | user   | main.py:42 | concern about race condition |

## Non-blocking (address or acknowledge)

| # | Author | File:Line | Comment |
|---|--------|-----------|---------|
| 1 | user   | utils.py:10 | nit: rename variable |
```

Comments without a blocking prefix are classified as non-blocking.

### 4. Suggest next steps

For each blocking comment, suggest the minimal fix. If the comment is a question,
draft a reply. If it requires a code change, identify the file and describe what to change.

## Anti-patterns

- Do not fetch the full PR diff. The comments already reference specific files and lines.
- Do not reply to or resolve comments automatically. Surface the information; let the user decide.
- Do not ignore bot comments silently. Filter them but mention the count.
