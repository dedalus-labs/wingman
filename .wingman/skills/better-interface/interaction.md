# Interaction

Focus management, key hints, modal flow, and feedback in terminal UIs.

## Focus Management

Focus is the primary navigation mechanism in a TUI. It must be obvious,
predictable, and never lost.

### Rules

- Exactly one widget has focus at any time
- Focus moves in a logical order (top-to-bottom, left-to-right)
- After closing a modal, focus returns to the widget that opened it
- After deleting an item, focus moves to the next item (not the previous)
- Tab cycles through focusable widgets; Shift+Tab goes backwards
- Never trap focus in a non-modal context

### Visual Indicator

The focused widget must be immediately identifiable:

```tcss
/* Good — clear focus state */
Input:focus {
  border: tall $accent;
  background: $surface-darken-1;
}

/* Bad — focus is only indicated by cursor position */
Input:focus {
  /* no visual change */
}
```

## Key Hints

Show available actions in a footer bar. Update contextually as the
user navigates.

### Format

```
key1 action1  key2 action2  key3 action3
```

- Keys are dimmed, actions are normal weight
- Separate pairs with 2+ spaces
- Show only contextually relevant keys (not every global binding)
- Put destructive actions (delete, quit without save) last

### Example

```python
# Good — contextual hints
def get_hints(self) -> str:
    if self.mode == "list":
        return "↑↓ navigate  Enter select  d delete  q quit"
    elif self.mode == "edit":
        return "Ctrl+S save  Esc cancel"
```

## Modal Flow

Modals must:

1. Capture all input (no key leaking to widgets behind)
2. Show a clear title and available actions
3. Be dismissible with Esc (cancel) and Enter (confirm)
4. Return focus to the opener on close
5. Dim or overlay the background to show modality

### Anti-patterns

- Modal that doesn't capture Tab (focus escapes to background)
- Modal with no Esc binding (user feels trapped)
- Stacked modals (modal opens another modal) — flatten the flow instead

## Feedback

### Immediate

Every action needs visible confirmation within one frame:

| Action | Feedback |
| --- | --- |
| Key press | Widget state changes visually |
| Submit form | Status message or transition |
| Delete item | Item disappears, focus moves |
| Error | Error message in status bar or inline |

### Async Operations

For anything that takes >100ms:

1. Show a spinner or "Loading..." immediately
2. Update with result when done
3. Show error inline if it fails — don't silently revert

```python
# Good — immediate feedback
self.status.update("Saving...")
await save()
self.status.update("Saved")

# Bad — no feedback during save
await save()
```
