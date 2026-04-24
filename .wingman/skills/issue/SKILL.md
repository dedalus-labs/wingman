---
name: issue
description: Create a GitHub issue using the wingman issue templates (bug, feature). Injects branch and commit context automatically.
allowed-tools: Bash(git *), Bash(gh *), Read
argument-hint: "<bug|feature> <title>"
---

## Context (auto-detected from HEAD)

- Current branch: !`git branch --show-current`
- Last commit: !`git log -1 --oneline`
- Remote: !`git remote get-url origin`

## Template Selection

Parse the first positional arg from `$ARGUMENTS` as the issue type:

| Type    | Template file                               | Labels              |
|---------|---------------------------------------------|---------------------|
| bug     | `.github/ISSUE_TEMPLATE/bug_report.yml`     | `bug,triage`        |
| feature | `.github/ISSUE_TEMPLATE/feature_request.yml`| `enhancement`       |

The `bug_report.yml` file is a GitHub issue form. `gh issue create --body` submits plain
markdown, so translate the yaml form fields into a markdown body with the same section
headings (Bug Description, Steps to Reproduce, Expected Behavior, Environment,
Additional Context).

For `feature_request.yml`, read the file and translate form fields the same way.

## Rules

- Issue title: short, imperative, no period, under 80 chars. No conventional-commit prefix
  (that's for PRs, not issues).
- The remaining positional args from `$ARGUMENTS` (after the type) form the title.
- Use `gh issue create --title "..." --body "$(cat <<'EOF' ... EOF)" --label "..."`.
- Labels come from the table above. Do not invent new labels.

## Task

1. Parse `$ARGUMENTS`:
   - First token: issue type (`bug` or `feature`). If missing or invalid,
     ask the user which template to use.
   - Remaining tokens: title.
2. Read the matching template file from `.github/ISSUE_TEMPLATE/`.
3. Fill every section. Leave no placeholder text. If a section truly has no content, write
   "N/A" rather than deleting the section.
4. Auto-inject the branch and last-commit context into "Additional Context".
5. Run `gh issue create` with the right labels.
6. Return the issue URL.
