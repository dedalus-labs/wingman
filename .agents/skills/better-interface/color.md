# Color

Palette consistency, contrast, and semantic color usage in terminal UIs.

## Color Hierarchy

Use 3-4 tiers. Every color in the palette belongs to exactly one tier.

| Tier | Purpose | Example (Tokyo Night) |
| --- | --- | --- |
| Primary | Key actions, active focus, links | `#7aa2f7` (blue) |
| Secondary | Labels, metadata, inactive tabs | `#565f89` (dim) |
| Muted | Borders, separators, background accents | `#3b4261` (very dim) |
| Semantic | Success, error, warning — state only | `#9ece6a`, `#f7768e`, `#e0af68` |

### Rules

- Never use semantic colors for decoration. Red means error. Green means success.
- Body text uses the default foreground — don't override it unless it's a label.
- Background colors should have enough contrast with text (4.5:1 minimum for
  accessibility, though terminal users typically tolerate lower).

## Consistency

Pick colors from one palette. Mixing hex values from different themes
creates visual noise.

```python
# Good — centralized palette
class Colors:
    PRIMARY = "#7aa2f7"
    DIM = "#565f89"
    BORDER = "#3b4261"
    ERROR = "#f7768e"
    SUCCESS = "#9ece6a"

# Bad — ad-hoc hex values scattered across widgets
label.styles.color = "#6699ff"    # close to primary but not quite
border.styles.color = "#444444"   # doesn't match the palette
```

## Dark-on-Dark Contrast

Terminal UIs are almost always dark mode. Common mistakes:

- Borders that are invisible against the background (too close in value)
- Dim text that disappears on some terminal themes
- Bright white text that causes eye strain

Test with at least two terminal themes (one dark, one light-on-dark)
to catch contrast issues.

## Focus Color

The focused widget gets the primary color on its border or background.
Everything else stays muted. This creates an immediate visual hierarchy
without any animation.

```tcss
Widget:focus {
  border: tall $primary;
}

Widget {
  border: tall $muted;
}
```
