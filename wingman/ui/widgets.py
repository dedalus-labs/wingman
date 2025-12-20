"""UI widgets for chat interface."""

from rich.markdown import Markdown
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, Static

from ..config import APP_CREDIT, APP_VERSION, MODELS
from ..context import ContextManager
from ..images import CachedImage, create_image_message_from_cache
from ..sessions import get_session, save_session
from .welcome import WELCOME_ART, WELCOME_ART_COMPACT


class ChatMessage(Static):
    """Single chat message."""

    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content

    def compose(self) -> ComposeResult:
        if self.role == "user":
            yield Static(Text.from_markup(f"[#7aa2f7]>[/] {self.content}"))
        else:
            yield Static(Text.from_markup("[bold #bb9af7]Assistant[/]"))
            yield Static(Markdown(self.content))


class Thinking(Static):
    """Minimal loading indicator."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._frame = 0

    def on_mount(self) -> None:
        self.set_interval(0.08, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(self.FRAMES)
        self.refresh()

    def render(self) -> Text:
        return Text.from_markup(f"[#7aa2f7]{self.FRAMES[self._frame]}[/]")


class ToolApproval(Static, can_focus=True):
    """Inline tool approval prompt like Claude Code."""

    BINDINGS = [
        Binding("1", "select_yes", "Yes", show=False),
        Binding("y", "select_yes", "Yes", show=False),
        Binding("2", "select_always", "Always", show=False),
        Binding("n", "select_no", "No", show=False),
        Binding("escape", "select_no", "No", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "confirm", "Confirm", show=False),
    ]

    def __init__(self, tool_name: str, command: str, **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.command = command
        self.result: str | None = None  # "yes", "always", "no"
        self._selected = 0  # 0=yes, 1=always, 2=no

    def on_mount(self) -> None:
        self.focus()

    def render(self) -> Text:
        short_cmd = self.command if len(self.command) <= 60 else self.command[:57] + "..."
        options = [
            ("1.", "Yes"),
            ("2.", "Yes, always allow"),
            ("n.", "No"),
        ]
        lines = [
            f"[bold #e0af68]{self.tool_name}[/]",
            f"  [#a9b1d6]{short_cmd}[/]",
            "",
        ]
        for i, (key, label) in enumerate(options):
            if i == self._selected:
                if i == 2:
                    lines.append(f"[#f7768e]› {key}[/] [bold]{label}[/]")
                else:
                    lines.append(f"[#9ece6a]› {key}[/] [bold]{label}[/]")
            else:
                lines.append(f"[dim]  {key} {label}[/]")
        return Text.from_markup("\n".join(lines))

    def action_move_up(self) -> None:
        self._selected = (self._selected - 1) % 3
        self.refresh()

    def action_move_down(self) -> None:
        self._selected = (self._selected + 1) % 3
        self.refresh()

    def action_confirm(self) -> None:
        if self._selected == 0:
            self.result = "yes"
        elif self._selected == 1:
            self.result = "always"
        else:
            self.result = "no"

    def action_select_yes(self) -> None:
        self.result = "yes"

    def action_select_always(self) -> None:
        self.result = "always"

    def action_select_no(self) -> None:
        self.result = "no"


class CommandStatus(Static):
    """Shows running command with pulsating dot."""

    def __init__(self, command: str, **kwargs):
        super().__init__(**kwargs)
        self.command = command
        self._pulse = 0
        self._status: str | None = None

    def on_mount(self) -> None:
        self.set_interval(0.15, self._tick)

    def _tick(self) -> None:
        self._pulse = (self._pulse + 1) % 6
        self.refresh()

    def set_status(self, status: str) -> None:
        self._status = status
        self.refresh()

    def render(self) -> Text:
        short_cmd = self.command if len(self.command) <= 50 else self.command[:47] + "..."

        if self._status == "success":
            dot = "[#9ece6a]•[/]"
            hint = ""
        elif self._status == "error":
            dot = "[#f7768e]•[/]"
            hint = ""
        elif self._status == "backgrounded":
            dot = "[#e0af68]•[/]"
            hint = "  [dim]backgrounded[/]"
        else:
            colors = ["#3d59a1", "#5a7ac7", "#7aa2f7", "#9fc5ff", "#7aa2f7", "#5a7ac7"]
            dot = f"[{colors[self._pulse]}]•[/]"
            hint = "  [dim]Ctrl+B to background[/]"

        return Text.from_markup(f"{dot} [dim]$ {short_cmd}[/]{hint}")


_panel_counter: int = 0


class ChatPanel(Vertical):
    """Self-contained chat panel with session, context, and input."""

    BINDINGS = [
        Binding("escape", "focus_input", "Focus Input", show=False),
    ]

    def __init__(self, panel_id: str | None = None, **kwargs):
        global _panel_counter
        if panel_id is None:
            _panel_counter += 1
            panel_id = f"panel-{_panel_counter}"
        super().__init__(id=panel_id, **kwargs)
        self.panel_id = panel_id
        self.session_id: str | None = None
        self.context = ContextManager(model=MODELS[0])
        self.pending_images: list[CachedImage] = []
        self.mcp_servers: list[str] = []
        self._is_active = False

    @property
    def messages(self) -> list[dict]:
        return self.context.messages

    @messages.setter
    def messages(self, value: list[dict]) -> None:
        self.context.set_messages(value)

    def compose(self) -> ComposeResult:
        with VerticalScroll(id=f"{self.panel_id}-scroll", classes="panel-scroll"):
            yield Vertical(id=f"{self.panel_id}-chat", classes="panel-chat")
        with Vertical(classes="panel-input"):
            yield Input(
                placeholder="Message... (/ for commands)",
                id=f"{self.panel_id}-prompt",
                classes="panel-prompt"
            )
            yield Static("", id=f"{self.panel_id}-hint", classes="panel-hint")

    def on_mount(self) -> None:
        self.call_after_refresh(self._show_welcome)

    def _show_welcome(self) -> None:
        chat = self.query_one(f"#{self.panel_id}-chat", Vertical)
        art = WELCOME_ART if self.size.width >= 70 else WELCOME_ART_COMPACT
        welcome = f"""{art}
[dim]v{APP_VERSION} · {APP_CREDIT}[/]

[#565f89]Type to chat · [bold #7aa2f7]/[/] for commands · [bold #7aa2f7]Ctrl+S[/] for sessions[/]"""
        chat.remove_children()
        chat.mount(Static(welcome, classes="panel-welcome"))

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self.set_class(active, "active-panel")
        if active:
            try:
                self.query_one(f"#{self.panel_id}-prompt", Input).focus()
            except Exception:
                pass

    def get_chat_container(self) -> Vertical:
        return self.query_one(f"#{self.panel_id}-chat", Vertical)

    def get_scroll_container(self) -> VerticalScroll:
        return self.query_one(f"#{self.panel_id}-scroll", VerticalScroll)

    def get_input(self) -> Input:
        return self.query_one(f"#{self.panel_id}-prompt", Input)

    def get_hint(self) -> Static:
        return self.query_one(f"#{self.panel_id}-hint", Static)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        chat = self.get_chat_container()
        chat.mount(ChatMessage(role, content))
        self.get_scroll_container().scroll_end(animate=False)

    def add_image_message(self, role: str, text: str, images: list[CachedImage]) -> None:
        msg = create_image_message_from_cache(text, images)
        self.messages.append(msg)
        chat = self.get_chat_container()
        img_indicator = f" [#7dcfff][{len(images)} image{'s' if len(images) != 1 else ''}][/]"
        display_text = (text or "(image)") + img_indicator
        chat.mount(ChatMessage(role, display_text))
        self.get_scroll_container().scroll_end(animate=False)

    def show_info(self, text: str) -> None:
        chat = self.get_chat_container()
        chat.mount(Static(f"[dim]{text}[/]"))
        self.get_scroll_container().scroll_end(animate=False)

    def clear_chat(self) -> None:
        self.context.clear()
        if self.session_id:
            save_session(self.session_id, [])
        chat = self.get_chat_container()
        chat.remove_children()

    def load_session(self, session_id: str) -> None:
        self.session_id = session_id
        self.messages = get_session(session_id)
        chat = self.get_chat_container()
        chat.remove_children()
        for msg in self.messages:
            if msg["role"] not in ("user", "assistant"):
                continue
            content = msg.get("content")
            if not content:
                continue
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                img_count = sum(1 for p in content if isinstance(p, dict) and p.get("type") == "image_url")
                display_text = " ".join(text_parts) or "(image)"
                if img_count:
                    display_text += f" [#7dcfff][{img_count} image{'s' if img_count != 1 else ''}][/]"
                chat.mount(ChatMessage(msg["role"], display_text))
            else:
                chat.mount(ChatMessage(msg["role"], content))
        self.get_scroll_container().scroll_end(animate=False)

    def action_focus_input(self) -> None:
        self.get_input().focus()
