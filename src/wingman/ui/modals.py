"""Modal dialogs and screens."""

import difflib

from dedalus_labs import AsyncDedalus
from rich.text import Text
from textual import on, work
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Static

from ..config import save_api_key


class APIKeyScreen(ModalScreen[str | None]):
    """Screen for entering Dedalus API key on first launch."""

    CSS = """
    APIKeyScreen {
        align: center middle;
        background: #1a1b26;
    }

    APIKeyScreen > Vertical {
        width: 70;
        height: auto;
        padding: 2 4;
    }

    APIKeyScreen .header {
        text-align: center;
        color: #7aa2f7;
        text-style: bold;
        padding-bottom: 2;
    }

    APIKeyScreen .instruction {
        text-align: center;
        color: #a9b1d6;
        padding-bottom: 1;
    }

    APIKeyScreen .link {
        text-align: center;
        color: #7aa2f7;
        text-style: underline;
        padding-bottom: 2;
    }

    APIKeyScreen .prompt {
        text-align: center;
        color: #a9b1d6;
        padding-bottom: 1;
    }

    APIKeyScreen Input {
        margin: 1 0;
    }

    APIKeyScreen .footer {
        text-align: center;
        color: #565f89;
        padding-top: 2;
    }

    APIKeyScreen .error {
        text-align: center;
        color: #f7768e;
        padding-top: 1;
    }

    APIKeyScreen .validating {
        text-align: center;
        color: #7aa2f7;
        padding-top: 1;
    }
    """

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

    CSS = """
    SelectionModal {
        align: center middle;
    }

    SelectionModal > Vertical {
        width: 60;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    SelectionModal ListView {
        height: auto;
        max-height: 15;
        margin-top: 1;
    }

    SelectionModal ListItem {
        padding: 0 1;
    }

    SelectionModal ListItem:hover {
        background: $primary 30%;
    }

    SelectionModal .title {
        text-style: bold;
        color: $text;
        padding-bottom: 1;
        border-bottom: solid $primary-background;
    }
    """

    def __init__(self, title: str, items: list[str], **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.items = items

    def compose(self):
        with Vertical():
            yield Label(self.title_text, classes="title")
            yield ListView(*[ListItem(Label(item), id=f"item-{i}") for i, item in enumerate(self.items)])

    @on(ListView.Selected)
    def on_select(self, event: ListView.Selected) -> None:
        idx = int(event.item.id.split("-")[1])
        self.dismiss(self.items[idx])

    def action_cancel(self) -> None:
        self.dismiss(None)


class InputModal(ModalScreen[str | None]):
    """Modal for text input."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    InputModal {
        align: center middle;
    }

    InputModal > Vertical {
        width: 60;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    InputModal .title {
        text-style: bold;
        padding-bottom: 1;
    }

    InputModal Input {
        margin-top: 1;
    }
    """

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

    CSS = """
    DiffModal {
        align: center middle;
    }

    DiffModal > Vertical {
        width: 90%;
        max-width: 100;
        height: auto;
        max-height: 80%;
        background: #1a1b26;
        border: solid #3b3d4d;
        padding: 1 2;
    }

    DiffModal .header {
        height: auto;
        padding-bottom: 1;
    }

    DiffModal .filepath {
        color: #565f89;
    }

    DiffModal .diff-view {
        height: auto;
        max-height: 20;
        overflow-y: auto;
        background: #16161e;
        padding: 1;
        border: solid #24283b;
    }

    DiffModal .hint {
        height: auto;
        color: #565f89;
        text-align: center;
        padding-top: 1;
    }
    """

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
            if line.startswith("+"):
                formatted.append(f"[#9ece6a]{line.rstrip()}[/]")
            elif line.startswith("-"):
                formatted.append(f"[#f7768e]{line.rstrip()}[/]")
            elif line.strip():
                formatted.append(f"[#a9b1d6]{line.rstrip()}[/]")

        diff_text = "\n".join(formatted) if formatted else "[dim]No visible changes[/]"

        display_path = self.path
        if len(display_path) > 60:
            display_path = "..." + display_path[-57:]

        with Vertical():
            with Vertical(classes="header"):
                yield Static(Text.from_markup("[bold #7aa2f7]Pending Edit[/]"))
                yield Static(Text.from_markup(f"[#565f89]{display_path}[/]"), classes="filepath")
            yield Static(Text.from_markup(diff_text), classes="diff-view")
            yield Static(
                Text.from_markup("[#9ece6a]y[/]/[#7aa2f7]Enter[/] approve    [#f7768e]n[/]/[#7aa2f7]Esc[/] reject"),
                classes="hint",
            )

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_reject(self) -> None:
        self.dismiss(False)
