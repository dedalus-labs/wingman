"""Modal dialogs and screens."""

import difflib
import time

from dedalus_labs import AsyncDedalus
from rich.markup import escape
from rich.text import Text
from textual import on, work
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Static

from ..config import save_api_key


class APIKeyScreen(ModalScreen[str | None]):
    """Screen for entering Dedalus API key on first launch."""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
    ]

    def compose(self):
        with Vertical():
            yield Static("One last thing...", classes="header")
            yield Static("Grab your Dedalus API key from:", classes="instruction")
            yield Static("→ https://www.dedaluslabs.ai/dashboard/api-keys", classes="link")
            yield Static("", classes="spacer")
            yield Static("...and paste it below to finish setup:", classes="prompt")
            yield Input(placeholder="Paste your API key here", id="api-key-input", password=True)
            yield Static("", id="api-key-status")
            yield Static("Your key is stored locally in ~/.wingman/config.json", classes="footer")

    def on_mount(self) -> None:
        self.query_one("#api-key-input", Input).focus()

    @on(Input.Submitted, "#api-key-input")
    def on_submit(self, event: Input.Submitted) -> None:
        key = event.value.strip()
        if key:
            self._validate_key(key)

    def action_quit(self) -> None:
        self.app.exit()

    @work(thread=False)
    async def _validate_key(self, key: str) -> None:
        status = self.query_one("#api-key-status", Static)
        input_widget = self.query_one("#api-key-input", Input)
        input_widget.disabled = True
        status.update("Validating...")
        status.set_classes("validating")

        if not key.startswith("dsk_"):
            status.update("Invalid key format. Key must start with dsk_")
            status.set_classes("error")
            input_widget.disabled = False
            input_widget.focus()
            return

        try:
            client = AsyncDedalus(api_key=key)
            await client.models.list()
            save_api_key(key)
            self.dismiss(key)
        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "invalid" in err_msg.lower() or "unauthorized" in err_msg.lower():
                status.update("Invalid API key. Please check and try again.")
            else:
                status.update(f"Connection error: {err_msg[:50]}")
            status.set_classes("error")
            input_widget.disabled = False
            input_widget.focus()


class SelectionModal(ModalScreen[str | None]):
    """Modal for selecting from a list."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, items: list[str], **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.items = items

    def compose(self):
        with Vertical():
            yield Label(self.title_text, classes="title")
            yield ListView(*[ListItem(Label(item), id=f"item-{i}") for i, item in enumerate(self.items)])
            yield Static("↑↓ navigate • Enter select • Esc/q cancel", classes="hint")

    @on(ListView.Highlighted)
    def on_highlight(self, event: ListView.Highlighted) -> None:
        if event.item:
            event.item.scroll_visible()

    @on(ListView.Selected)
    def on_select(self, event: ListView.Selected) -> None:
        idx = int(event.item.id.split("-")[1])
        self.dismiss(self.items[idx])

    def action_cancel(self) -> None:
        self.dismiss(None)


class MemoryModal(ModalScreen[tuple[str, str | None] | None]):
    """Modal for browsing and managing project memory."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel"),
        Binding("d", "delete", "Delete"),
        Binding("a", "add", "Add"),
    ]

    def __init__(self, entries: list, **kwargs):
        super().__init__(**kwargs)
        self.entries = entries  # list[MemoryEntry]
        self._highlighted_idx: int = 0
        self._pending_delete: bool = False

    def compose(self):
        with Vertical():
            yield Label("Project Memory", classes="title")
            if self.entries:
                items = []
                for i, e in enumerate(self.entries):
                    ts = time.strftime("%m/%d %H:%M", time.localtime(e.created_at))
                    preview = e.content[:60].replace("\n", " ")
                    if len(e.content) > 60:
                        preview += "..."
                    items.append(ListItem(Label(f"[dim]{e.id}[/] [{ts}] {preview}"), id=f"mem-{i}"))
                yield ListView(*items)
                yield Static("", id="preview-text", classes="preview")
                yield Static("↑↓ navigate • d delete • a add • Esc/q close", classes="hint")
            else:
                yield Static("No memories saved.\nUse 'a' to add or /memory add <text>", classes="empty")
                yield Static("a add • Esc/q close", classes="hint")

    def on_mount(self) -> None:
        if self.entries:
            self._update_preview(0)

    @on(ListView.Highlighted)
    def on_highlight(self, event: ListView.Highlighted) -> None:
        if event.item:
            event.item.scroll_visible()
            idx = int(event.item.id.split("-")[1])
            self._highlighted_idx = idx
            self._pending_delete = False  # Reset on navigation
            self._update_preview(idx)
            self._update_hint()

    def _update_preview(self, idx: int) -> None:
        try:
            preview = self.query_one("#preview-text", Static)
            if 0 <= idx < len(self.entries):
                content = self.entries[idx].content
                # Show first few lines
                lines = content.split("\n")[:3]
                preview.update("\n".join(lines) + ("..." if len(content.split("\n")) > 3 else ""))
        except Exception:
            pass

    def action_delete(self) -> None:
        if not self.entries or not (0 <= self._highlighted_idx < len(self.entries)):
            return
        if self._pending_delete:
            # Confirmed - delete
            entry_id = self.entries[self._highlighted_idx].id
            self.dismiss(("delete", entry_id))
        else:
            # First press - ask for confirmation
            self._pending_delete = True
            self._update_hint()

    def _update_hint(self) -> None:
        try:
            hint = self.query_one(".hint", Static)
            if self._pending_delete:
                hint.update("[#f7768e]Press d again to confirm delete[/] • Esc/q cancel")
            else:
                hint.update("↑↓ navigate • d delete • a add • Esc/q close")
        except Exception:
            pass

    def action_add(self) -> None:
        self.dismiss(("add", None))

    def action_cancel(self) -> None:
        self.dismiss(None)


class MCPModal(ModalScreen[tuple[str, str | None] | None]):
    """Modal for browsing and managing MCP servers."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel"),
        Binding("d", "delete", "Delete"),
        Binding("a", "add", "Add"),
    ]

    def __init__(self, servers: list[str], **kwargs):
        super().__init__(**kwargs)
        self.servers = servers
        self._highlighted_idx: int = 0
        self._pending_delete: bool = False

    def compose(self):
        with Vertical():
            yield Label("MCP Servers", classes="title")
            if self.servers:
                items = [ListItem(Label(f"{i+1}. {s}"), id=f"mcp-{i}") for i, s in enumerate(self.servers)]
                yield ListView(*items)
                yield Static("↑↓ navigate • d delete • a add • Esc/q close", classes="hint")
            else:
                yield Static("No MCP servers configured.\nUse 'a' to add or Ctrl+G", classes="empty")
                yield Static("a add • Esc/q close", classes="hint")

    @on(ListView.Highlighted)
    def on_highlight(self, event: ListView.Highlighted) -> None:
        if event.item:
            event.item.scroll_visible()
            idx = int(event.item.id.split("-")[1])
            self._highlighted_idx = idx
            self._pending_delete = False
            self._update_hint()

    def action_delete(self) -> None:
        if not self.servers or not (0 <= self._highlighted_idx < len(self.servers)):
            return
        if self._pending_delete:
            server = self.servers[self._highlighted_idx]
            self.dismiss(("delete", server))
        else:
            self._pending_delete = True
            self._update_hint()

    def _update_hint(self) -> None:
        try:
            hint = self.query_one(".hint", Static)
            if self._pending_delete:
                hint.update("[#f7768e]Press d again to confirm delete[/] • Esc/q cancel")
            else:
                hint.update("↑↓ navigate • d delete • a add • Esc/q close")
        except Exception:
            pass

    def action_add(self) -> None:
        self.dismiss(("add", None))

    def action_cancel(self) -> None:
        self.dismiss(None)


class InputModal(ModalScreen[str | None]):
    """Modal for text input."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, placeholder: str = "", **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.placeholder = placeholder

    def compose(self):
        with Vertical():
            yield Label(self.title_text, classes="title")
            yield Input(placeholder=self.placeholder, id="modal-input")

    def on_mount(self) -> None:
        self.query_one("#modal-input", Input).focus()

    @on(Input.Submitted, "#modal-input")
    def on_submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value if event.value.strip() else None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class DiffModal(ModalScreen[bool]):
    """Modal showing a diff with approve/reject buttons."""

    BINDINGS = [
        Binding("y", "approve", "Approve"),
        Binding("enter", "approve", "Approve"),
        Binding("n", "reject", "Reject"),
        Binding("escape", "reject", "Reject"),
        Binding("q", "reject", "Reject"),
    ]

    CONTEXT_LINES = 3

    def __init__(self, path: str, old_string: str, new_string: str, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.old_string = old_string
        self.new_string = new_string

    def _get_diff_with_context(self) -> str:
        """Generate diff with surrounding file context and line numbers."""
        from pathlib import Path

        old_lines = self.old_string.splitlines() if self.old_string else []
        new_lines = self.new_string.splitlines() if self.new_string else []

        # Try to read the actual file for context
        match_start = 0
        file_lines: list[str] = []
        try:
            file_path = Path(self.path)
            if file_path.exists():
                file_content = file_path.read_text()
                file_lines = file_content.splitlines()

                # Find where old_string starts in the file
                if old_lines:
                    for i in range(len(file_lines) - len(old_lines) + 1):
                        if file_lines[i : i + len(old_lines)] == old_lines:
                            match_start = i
                            break
        except Exception:
            pass

        ctx = self.CONTEXT_LINES
        change_len = max(len(old_lines), len(new_lines), 1)
        start = max(0, match_start - ctx)
        end = min(len(file_lines), match_start + len(old_lines) + ctx) if file_lines else 0

        # Compute line number width
        max_line = max(end, match_start + change_len) + len(new_lines)
        num_width = max(len(str(max_line)), 2)

        formatted = []

        # Context before (from file)
        for i in range(start, match_start):
            ln = str(i + 1).rjust(num_width)
            formatted.append(f"[#565f89]{ln}   {escape(file_lines[i])}[/]")

        # Show removed lines (old_string)
        for i, line in enumerate(old_lines):
            ln = str(match_start + i + 1).rjust(num_width)
            formatted.append(f"[#f7768e]{ln} - {escape(line)}[/]")

        # Show added lines (new_string)
        for i, line in enumerate(new_lines):
            ln = str(match_start + i + 1).rjust(num_width)
            formatted.append(f"[#9ece6a]{ln} + {escape(line)}[/]")

        # Context after (from file)
        ctx_start = match_start + len(old_lines)
        for i in range(ctx_start, end):
            # Line numbers after change account for size difference
            actual_line = i + 1 + (len(new_lines) - len(old_lines))
            ln = str(actual_line).rjust(num_width)
            formatted.append(f"[#565f89]{ln}   {escape(file_lines[i])}[/]")

        return "\n".join(formatted) if formatted else "[dim]No visible changes[/]"

    def compose(self):
        diff_text = self._get_diff_with_context()

        display_path = self.path
        if len(display_path) > 60:
            display_path = "..." + display_path[-57:]

        with Vertical():
            with Vertical(classes="header"):
                yield Static(Text.from_markup("[bold #7aa2f7]Pending Edit[/]"))
                yield Static(Text.from_markup(f"[#565f89]{escape(display_path)}[/]"), classes="filepath")
            yield Static(Text.from_markup(diff_text), classes="diff-view")
            yield Static(
                Text.from_markup(
                    "[#9ece6a]y[/]/[#7aa2f7]Enter[/] approve    [#f7768e]n[/]/[#7aa2f7]Esc[/]/q reject"
                ),
                classes="hint",
            )

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_reject(self) -> None:
        self.dismiss(False)
