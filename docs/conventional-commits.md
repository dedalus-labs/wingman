# Conventional Commit Messages

See how a minor change to your commit message style can make a difference.

```
git commit -m"<type>(<optional scope>): <description>" \
  -m"<optional body>" \
  -m"<optional footer>"
```

> **Note:** This cheatsheet is opinionated but does not violate the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Commit Message Formats

### General Commit

```
<type>(<optional scope>): <description>

<optional body>

<optional footer>
```

### Initial Commit

```
chore: init
```

## Types

**Changes relevant to the API or functionality:**

- `feat` — Commits that add or adjust a feature
- `fix` — Commits that fix a bug

**Internal changes:**

- `refactor` — Rewrite or restructure code without changing behavior
- `perf` — Special `refactor` that improves performance
- `style` — Code style changes (whitespace, formatting) without behavior change
- `test` — Add missing tests or correct existing ones
- `docs` — Documentation only changes
- `build` — Build system, dependencies, CI/CD changes
- `ci` — CI configuration changes
- `chore` — Miscellaneous (e.g., `.gitignore`)

## Scopes

The `scope` provides additional context. It's **optional** but encouraged.

**Wingman scopes:**

- `ui` — TUI components and widgets
- `commands` — Chat commands (/new, /model, etc.)
- `sessions` — Session management
- `checkpoints` — Checkpoint/rollback
- `config` — Configuration
- `tools` — Agent tools
- `export` — Export/import

**Do not** use issue identifiers as scopes.

## Breaking Changes

Breaking changes **must** be indicated by `!` before the `:`:

```
feat(config)!: change config file location
```

Or include a footer:

```
feat(config): new config system

BREAKING CHANGE: Config now stored in ~/.config/wingman instead of ~/.wingman
```

## Description

The `description` is a concise summary:

- **Mandatory**
- Use imperative, present tense: "add" not "added" or "adds"
- Think: "This commit will... add keyboard shortcuts"
- **Do not** capitalize the first letter
- **Do not** end with a period

## Versioning Impact

Your commits determine the next version:

| Commit Type          | Version Bump  |
| -------------------- | ------------- |
| `feat`               | Minor (0.X.0) |
| `fix`                | Patch (0.0.X) |
| `perf`               | Patch (0.0.X) |
| Breaking change (`!`) | Major (X.0.0) |
| Others               | No release    |

## Examples

```
feat(ui): add keyboard shortcuts modal
```

```
fix(sessions): handle empty chat history gracefully
```

```
feat(commands): add /export markdown format

Exports current session to markdown file.

Closes #42
```

```
perf(ui): reduce re-renders on message updates
```

```
docs: update installation instructions
```

## References

- https://www.conventionalcommits.org/
- https://github.com/googleapis/release-please


