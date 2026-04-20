# Layout

Alignment, spacing, and responsive sizing for terminal UIs.

## Spacing Scale

Use consistent cell-based spacing: 0, 1, 2, 4. Textual CSS `padding`
and `margin` are in cell units (not pixels).

```tcss
/* Good — consistent spacing */
#sidebar {
  padding: 1 2;
  margin: 0 1;
}

#content {
  padding: 1 2;
}

/* Bad — arbitrary spacing */
#sidebar {
  padding: 1 3;
  margin: 0 2;
}

#content {
  padding: 2 1;
}
```

## Responsive Sizing

TUI must work at 80x24 minimum. Use fractional units and min/max
constraints.

```tcss
/* Good — adapts to terminal width */
#sidebar {
  width: 1fr;
  min-width: 20;
  max-width: 40;
}

#main {
  width: 3fr;
}

/* Bad — fixed width breaks on small terminals */
#sidebar {
  width: 30;
}
```

## Content Regions

Split the screen into clear regions: header, content, footer. The
content region gets all remaining space via `1fr`. Header and footer
are fixed height.

```tcss
Screen {
  layout: vertical;
}

#header {
  height: 1;
  dock: top;
}

#footer {
  height: 1;
  dock: bottom;
}

#content {
  height: 1fr;
}
```

## Alignment

- Left-align labels and values in forms
- Right-align numeric columns in tables
- Center titles only when the container is narrow (< 40 cols)
- Use `content-align: center middle` for empty states and loading screens

## Overflow

Content that doesn't fit must degrade gracefully:

- Truncate long strings with ellipsis via `overflow: hidden`
- Scroll vertically in content regions, never horizontally
- Collapse optional columns in tables when terminal is narrow
