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
    ]

    def __init__(self, title: str, items: list[str], **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.items = items

    def compose(self):
        with Vertical():
            yield Label(self.title_text, classes="title")
            yield ListView(*[ListItem(Label(item), id=f"item-{i}") for i, item in enumerate(self.items)])
            yield Static("↑↓ navigate • Enter select • Esc cancel", classes="hint")

    @on(ListView.Highlighted)
    def on_highlight(self, event: ListView.Highlighted) -> None:
        """Scroll highlighted item into view."""
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
                yield Static("↑↓ navigate • d delete • a add • Esc close", classes="hint")
            else:
                yield Static("No memories saved.\nUse 'a' to add or /memory add <text>", classes="empty")
                yield Static("a add • Esc close", classes="hint")

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
                hint.update("[#f7768e]Press d again to confirm delete[/] • Esc cancel")
            else:
                hint.update("↑↓ navigate • d delete • a add • Esc close")
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
    ]

    def __init__(self, path: str, old_string: str, new_string: str, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.old_string = old_string
        self.new_string = new_string

    def compose(self):
        diff_lines = list(
            difflib.unified_diff(
                self.old_string.splitlines(keepends=True),
                self.new_string.splitlines(keepends=True),
                lineterm="",
            )
        )

        formatted = []
        for line in diff_lines:
            if line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
                continue
            escaped = escape(line.rstrip())
            if line.startswith("+"):
                formatted.append(f"[#9ece6a]{escaped}[/]")
            elif line.startswith("-"):
                formatted.append(f"[#f7768e]{escaped}[/]")
            elif line.strip():
                formatted.append(f"[#a9b1d6]{escaped}[/]")

        diff_text = "\n".join(formatted) if formatted else "[dim]No visible changes[/]"

        display_path = self.path
        if len(display_path) > 60:
            display_path = "..." + display_path[-57:]

        with Vertical():
            with Vertical(classes="header"):
                yield Static(Text.from_markup(f"[bold #7aa2f7]Pending Edit[/]"))
                yield Static(Text.from_markup(f"[#565f89]{escape(display_path)}[/]"), classes="filepath")
            yield Static(Text.from_markup(diff_text), classes="diff-view")
            yield Static(
                Text.from_markup("[#9ece6a]y[/]/[#7aa2f7]Enter[/] approve    [#f7768e]n[/]/[#7aa2f7]Esc[/] reject"),
                classes="hint",
            )

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_reject(self) -> None:
        self.dismiss(False)
