---
name: better-interface
description: Design engineering principles for making TUI interfaces feel polished. Use when building Textual widgets, reviewing TUI code, implementing transitions, focus states, alignment, spacing, or any visual detail work. Triggers on TUI polish, design details, "make it feel better", "feels off", layout alignment, color consistency, responsive sizing.
---

# Details that make TUI interfaces feel better

Great TUIs rarely come from a single thing. It's a collection of small details that compound into a professional experience. Apply these principles when building or reviewing Textual/terminal UI code.

## Quick Reference

| Category | When to Use |
| --- | --- |
| [Layout](layout.md) | Alignment, spacing, responsive sizing, content regions |
| [Color](color.md) | Palette consistency, contrast, semantic color usage |
| [Interaction](interaction.md) | Focus management, key hints, modal flow, feedback |
| [Typography](typography.md) | Text truncation, wrapping, Unicode, monospace alignment |

## Core Principles

### 1. Consistent Spacing

Use a spacing scale (1, 2, 4 cells). Mismatched padding between related
elements is the most common thing that makes TUIs feel off. Textual's
`padding` and `margin` CSS properties use cell units.

### 2. Optical Alignment Over Grid Alignment

When geometric centering looks wrong in a terminal, adjust optically.
Asymmetric Unicode characters (arrows, bullets) and mixed-width content
need manual nudging. A centered title above left-aligned content often
needs 1 cell of left padding removed.

### 3. Color Hierarchy

Use 3-4 color tiers consistently:
- **Primary**: key actions, active focus (bright, saturated)
- **Secondary**: labels, metadata (dimmed)
- **Muted**: borders, separators (very dim)
- **Danger/Success**: semantic states only (red/green)

Never use bright colors for passive elements. Reserve saturation for
things the user needs to notice.

### 4. Focus is Sacred

The focused widget must be visually distinct at a glance. Use border
color changes, not just cursor position. A user glancing at the screen
should instantly know where input will go.

### 5. Responsive Layout

TUI must work at 80x24 minimum. Use `fr` units and `max-width`/
`min-width` in Textual CSS to adapt. Content that overflows should
truncate with ellipsis, never wrap into garbage.

### 6. Feedback on Every Action

Every keypress that does something should produce visible feedback
within one frame. If an operation takes time, show a spinner or
status message immediately — don't let the user wonder if their
input was received.

### 7. Subtle Transitions

Textual supports CSS transitions. Use short durations (150-300ms)
for background color and opacity changes on hover/focus. Never
animate layout properties (width, height) — terminal reflow is
not smooth.

### 8. Border Consistency

Pick one border style and stick with it. `tall` for primary
containers, `round` for cards/modals, `heavy` for emphasis. Mixing
`ascii`, `tall`, `round`, and `heavy` in one screen looks
incoherent.

### 9. Key Hints

Always show available keys in a footer or status bar. Format as
`key action` pairs separated by thin spaces. Dim the keys relative
to the actions. Update hints contextually as focus moves.

### 10. Content Density

Terminal space is precious. Default to dense layouts. Use blank
lines only to separate logical groups, never for decoration.
Single-line headers over multi-line. Abbreviate labels when
the full form is obvious from context.

## Common Mistakes

| Mistake | Fix |
| --- | --- |
| Inconsistent padding between similar widgets | Use a spacing constant |
| Bright colors on passive/decorative elements | Reserve bright for actions and focus |
| No visible focus indicator | Add border color or background change on focus |
| Content overflows and wraps badly | Set `overflow: hidden` with `text-overflow: ellipsis` |
| No key hints visible | Add contextual footer with available actions |
| Large empty regions at default size | Use `fr` units to distribute space |
| Mixed border styles in one view | Standardize on one style per element tier |
| No feedback on async operations | Show spinner/status immediately on action |

## Review Checklist

- [ ] Spacing is consistent between related elements
- [ ] Focused widget is visually distinct (border or background)
- [ ] Color usage follows the 3-4 tier hierarchy
- [ ] Layout works at 80x24 minimum terminal size
- [ ] Long text truncates with ellipsis, never wraps into garbage
- [ ] Key hints are visible and contextually updated
- [ ] Every user action produces visible feedback
- [ ] Border styles are consistent within each tier
- [ ] No bright colors on passive elements
- [ ] Transitions are short (150-300ms) and only on color/opacity

## Reference Files

- [layout.md](layout.md) — Alignment, spacing, responsive sizing
- [color.md](color.md) — Palette consistency, contrast, semantic usage
- [interaction.md](interaction.md) — Focus management, key hints, modals
- [typography.md](typography.md) — Truncation, wrapping, Unicode alignment
