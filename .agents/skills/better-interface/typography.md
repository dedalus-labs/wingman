# Typography

Text truncation, wrapping, Unicode alignment, and monospace rendering in terminal UIs.

## Truncation

Long text must truncate with ellipsis, never wrap into a broken layout.

```tcss
/* Good — truncate with ellipsis */
.filename {
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
}
```

### Where to Truncate

| Content | Truncate? | Where |
| --- | --- | --- |
| File paths | Yes | From the left (`...rc/wingman/app.py`) |
| Chat messages | No | Let them wrap within the message area |
| Status text | Yes | From the right with ellipsis |
| Titles/headings | Yes | From the right with ellipsis |
| Table cells | Yes | From the right, keep header visible |

## Wrapping

Within content areas (chat messages, descriptions), wrapping is expected.
Use Textual's default wrapping behavior. But:

- Never break mid-word for English text
- Code blocks should scroll horizontally, not wrap
- Wrap at the container boundary, not at an arbitrary column

## Unicode and Box Drawing

Terminal UIs use Unicode box-drawing characters for borders and trees.
Consistency matters:

- Use one weight: light (`─ │ ┌ ┐ └ ┘`) or heavy (`━ ┃ ┏ ┓ ┗ ┛`)
- Don't mix rounded (`╭ ╮ ╰ ╯`) with square corners in the same widget
- Tree connectors: `├── └── │` — be consistent with trailing spaces

### Width Issues

Some Unicode characters are double-width in terminals (CJK, some emoji).
This breaks alignment in tables and fixed-width layouts.

```python
# Good — use unicodedata to measure actual display width
import unicodedata

def display_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)

# Bad — using len() for alignment
pad = " " * (20 - len(text))  # wrong if text contains wide chars
```

## Monospace Alignment

Terminal text is monospace, which makes alignment easy — if you respect it:

- Align columns with spaces, never tabs (tab width varies by terminal)
- Right-align numbers in columns
- Pad shorter strings to column width

```python
# Good — aligned columns
f"{'Name':<20} {'Size':>8} {'Modified':<12}"
f"{'app.py':<20} {'1.2 KB':>8} {'2024-01-15':<12}"

# Bad — no alignment
f"Name: {name} Size: {size} Modified: {modified}"
```

## Emphasis

In a terminal, you have limited tools for emphasis:

| Technique | Use for | Textual markup |
| --- | --- | --- |
| Bold | Section titles, key values | `[bold]text[/bold]` |
| Dim | Metadata, secondary info | `[dim]text[/dim]` |
| Color | Semantic meaning (see color.md) | `[#7aa2f7]text[/]` |
| Reverse | Selected items in lists | `[reverse]text[/reverse]` |

Never combine more than two: bold + color is fine, bold + dim + italic + color is noise.
