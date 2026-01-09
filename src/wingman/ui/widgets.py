"""UI widgets for chat interface."""

import random
import time
from dataclasses import dataclass
from pathlib import Path

from rich.markdown import Markdown
from rich.markup import escape
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Input, Static

from ..bulletin import get_bulletin_manager
from ..command_completion import CompletionContext, apply_completion, get_completion_context, resolve_completion
from ..config import APP_CREDIT, APP_VERSION, MODELS
from ..context import ContextManager
from ..images import IMAGE_EXTENSIONS, CachedImage, create_image_message_from_cache
from ..sessions import get_session, get_session_working_dir, save_session
from .welcome import WELCOME_ART, WELCOME_ART_COMPACT


@dataclass
class _CompletionCycle:
    candidates: list[str]
    include_slash: bool
    replace_start: int
    replace_end: int
    kind: str
    value: str
    cursor_position: int
    index: int

    @classmethod
    def from_context(
        cls,
        context: CompletionContext,
        value: str,
        cursor_position: int,
        index: int,
    ) -> "_CompletionCycle":
        replacement = f"/{context.candidates[index]}" if context.include_slash else context.candidates[index]
        return cls(
            candidates=context.candidates,
            include_slash=context.include_slash,
            replace_start=context.replace_start,
            replace_end=context.replace_start + len(replacement),
            kind=context.kind,
            value=value,
            cursor_position=cursor_position,
            index=index,
        )

    def is_active_for(self, value: str, cursor_position: int) -> bool:
        return self.value == value and self.cursor_position == cursor_position

    def next_index(self) -> int:
        return (self.index + 1) % len(self.candidates)

    def to_context(self, value: str, cursor_position: int) -> CompletionContext:
        return CompletionContext(
            value=value,
            cursor_position=cursor_position,
            candidates=self.candidates,
            prefix="",
            replace_start=self.replace_start,
            replace_end=self.replace_end,
            include_slash=self.include_slash,
            kind=self.kind,
        )

    def advance(self, index: int, value: str, cursor_position: int) -> "_CompletionCycle":
        replacement = f"/{self.candidates[index]}" if self.include_slash else self.candidates[index]
        return _CompletionCycle(
            candidates=self.candidates,
            include_slash=self.include_slash,
            replace_start=self.replace_start,
            replace_end=self.replace_start + len(replacement),
            kind=self.kind,
            value=value,
            cursor_position=cursor_position,
            index=index,
        )


class MultilineInput(Input):
    """Input that joins pasted multi-line text, clears on escape, and collapses long pastes."""

    LONG_PASTE_THRESHOLD = 200

    BINDINGS = [
        Binding("ctrl+a", "select_all", "Select All", show=False),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pasted_content: str | None = None
        self._paste_placeholder: str | None = None
        self._completion_cycle: _CompletionCycle | None = None

    def _on_key(self, event) -> None:
        if event.key == "tab" and self._handle_tab_completion():
            event.stop()
            event.prevent_default()
            return
        if event.key != "tab":
            self._completion_cycle = None
        # Let typing proceed normally - user can type after the placeholder
        # Content will be expanded on submit via get_submit_value()
        super()._on_key(event)

    def _handle_tab_completion(self) -> bool:
        if not self.value.lstrip().startswith("/"):
            return False
        if not self.selection.is_empty:
            self._completion_cycle = None
            return True
        if self._completion_cycle and self._completion_cycle.is_active_for(self.value, self.cursor_position):
            self._apply_cycle_candidate(self._completion_cycle.next_index())
            return True
        context = get_completion_context(self.value, self.cursor_position)
        if context is None or not context.candidates:
            self._completion_cycle = None
            return True
        completion = resolve_completion(context.prefix, context.candidates)
        if completion is not None:
            result = apply_completion(context, completion, add_space=len(context.candidates) == 1)
            self.value = result.value
            self.cursor_position = result.cursor_position
            self._completion_cycle = None
            return True
        self._start_completion_cycle(context)
        return True

    def _on_paste(self, event: events.Paste) -> None:
        self._completion_cycle = None
        if event.text:
            # Check if this looks like an image path - don't collapse those
            text_lower = event.text.lower().strip().strip("'\"")
            is_image = any(text_lower.endswith(ext) for ext in IMAGE_EXTENSIONS) or (
                text_lower.startswith("file://")
                and any(ext in text_lower for ext in IMAGE_EXTENSIONS)
            )

            if is_image:
                # For image paths, preserve the path exactly (just trim whitespace)
                cleaned = event.text.strip()
                self._pasted_content = None
                self._paste_placeholder = None
                selection = self.selection
                if selection.is_empty:
                    self.insert_text_at_cursor(cleaned)
                else:
                    self.replace(cleaned, *selection)
            else:
                # For regular text, join multiple lines
                cleaned = " ".join(event.text.split())

                if len(cleaned) > self.LONG_PASTE_THRESHOLD:
                    self._pasted_content = cleaned
                    self._paste_placeholder = f"[pasted {len(cleaned)} chars]"
                    # Insert placeholder at cursor, preserving existing text
                    selection = self.selection
                    if selection.is_empty:
                        self.insert_text_at_cursor(self._paste_placeholder)
                    else:
                        self.replace(self._paste_placeholder, *selection)
                else:
                    self._pasted_content = None
                    self._paste_placeholder = None
                    selection = self.selection
                    if selection.is_empty:
                        self.insert_text_at_cursor(cleaned)
                    else:
                        self.replace(cleaned, *selection)
        event.stop()
        event.prevent_default()

    def get_submit_value(self) -> str:
        """Get the actual value to submit (expanded paste + any additional text)."""
        if self._pasted_content is not None and self._paste_placeholder is not None:
            # Find placeholder in value and replace with actual pasted content
            if self._paste_placeholder in self.value:
                content = self.value.replace(self._paste_placeholder, self._pasted_content, 1)
            else:
                # Placeholder was edited/removed, just use current value
                content = self.value
            self._pasted_content = None
            self._paste_placeholder = None
            return content
        return self.value

    def _get_panel(self) -> "ChatPanel | None":
        for ancestor in self.ancestors_with_self:
            if isinstance(ancestor, ChatPanel):
                return ancestor
        return None

    def _start_completion_cycle(self, context: CompletionContext) -> None:
        if not context.candidates:
            self._completion_cycle = None
            return
        result = apply_completion(context, context.candidates[0], add_space=False)
        self.value = result.value
        self.cursor_position = result.cursor_position
        self._completion_cycle = _CompletionCycle.from_context(context, result.value, result.cursor_position, index=0)
        self._update_cycle_hint()

    def _apply_cycle_candidate(self, candidate_index: int) -> None:
        if not self._completion_cycle:
            return
        candidate = self._completion_cycle.candidates[candidate_index]
        context = self._completion_cycle.to_context(self.value, self.cursor_position)
        result = apply_completion(context, candidate, add_space=False)
        self.value = result.value
        self.cursor_position = result.cursor_position
        self._completion_cycle = self._completion_cycle.advance(
            candidate_index,
            result.value,
            result.cursor_position,
        )
        self._update_cycle_hint()

    def _update_cycle_hint(self) -> None:
        """Update hint to show cycling candidates with current selection highlighted."""
        panel = self._get_panel()
        if not panel or not self._completion_cycle:
            return
        hint = panel.get_hint()
        candidates = self._completion_cycle.candidates
        current_idx = self._completion_cycle.index
        parts = []
        for i, cand in enumerate(candidates):
            if i == current_idx:
                parts.append(f"[bold #9ece6a]{cand}[/]")
            else:
                parts.append(f"[#7aa2f7]{cand}[/]")
        hint.update("  ".join(parts))

class ChatMessage(Static):
    """Single chat message."""

    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content

    def compose(self) -> ComposeResult:
        if self.role == "user":
            yield Static(Text.from_markup(f"[#7aa2f7]>[/] {escape(self.content)}"))
        else:
            yield Static(Text.from_markup("[bold #bb9af7]Assistant[/]"))
            yield Static(Markdown(self.content))


class Thinking(Static):
    """Loading indicator with dynamic status label."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    IDLE_LABELS = ["Mazing", "Soaring", "Ascending Olympus", "Weaving fate", "Consulting the Oracle"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._frame = 0
        self._status: str | None = None
        self._idle_label = random.choice(self.IDLE_LABELS)

    def on_mount(self) -> None:
        self.set_interval(0.08, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(self.FRAMES)
        self.refresh()

    def set_status(self, status: str | None) -> None:
        """Update the status label (e.g., 'Reading config.py')."""
        self._status = status
        self.refresh()

    def render(self) -> Text:
        spinner = f"[#e0af68]{self.FRAMES[self._frame]}[/]"
        if self._status:
            return Text.from_markup(f"{spinner} [#a9b1d6]{escape(self._status)}[/]")
        return Text.from_markup(f"{spinner} [dim #a9b1d6]{self._idle_label}...[/]")


class StreamingText(Static):
    """Widget for displaying streaming text content in real-time."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._content = ""

    def append_text(self, text: str) -> None:
        """Append text to the streaming content."""
        self._content += text
        self.update(Text.from_markup(f"[#c0caf5]{escape(self._content)}[/]"))

    def mark_complete(self) -> None:
        """Ensure final content is displayed, stripped of trailing whitespace."""
        self._content = self._content.rstrip()
        self.update(Text.from_markup(f"[#c0caf5]{escape(self._content)}[/]"))


class ToolApproval(Vertical, can_focus=True):
    """Inline tool approval prompt like Claude Code."""

    BINDINGS = [
        Binding("y", "select_yes", "Yes", show=False),
        Binding("a", "select_always", "Always", show=False),
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
        self.result: tuple[str, str] | None = None  # ("yes"/"always"/"no", feedback)
        self._selected = 0  # 0=yes, 1=always, 2=no
        self._feedback_mode = False

    def compose(self) -> ComposeResult:
        yield Static(id="approval-content")
        with Horizontal(id="approval-input-row", classes="hidden"):
            yield Static("[#7aa2f7]>[/] ", id="approval-prompt")
            yield Input(placeholder="What should I do instead?", id="approval-feedback")

    def on_mount(self) -> None:
        self._update_display()
        self.focus()

    def _update_display(self) -> None:
        content = self.query_one("#approval-content", Static)
        input_row = self.query_one("#approval-input-row", Horizontal)
        feedback_input = self.query_one("#approval-feedback", Input)

        if self._feedback_mode:
            lines = [
                f"[bold #e0af68]{escape(self.tool_name)}[/]",
                f"  [dim]{escape(self.command)}[/]",
            ]
            content.update(Text.from_markup("\n".join(lines)))
            input_row.remove_class("hidden")
            feedback_input.focus()
        else:
            options = [
                ("y.", "Yes", "#9ece6a"),
                ("a.", "Yes, always allow this session", "#9ece6a"),
                ("n.", "No, and tell me what to do differently", "#f7768e"),
            ]
            lines = [
                f"[bold #e0af68]{escape(self.tool_name)}[/]",
                f"  [dim]{escape(self.command)}[/]",
                "",
                "[#a9b1d6]Do you want to proceed?[/]",
            ]
            for i, (key, label, color) in enumerate(options):
                if i == self._selected:
                    lines.append(f"[{color}]› {key}[/] [bold]{label}[/]")
                else:
                    lines.append(f"[dim]  {key} {label}[/]")
            content.update(Text.from_markup("\n".join(lines)))
            input_row.add_class("hidden")

    def action_move_up(self) -> None:
        if not self._feedback_mode:
            self._selected = (self._selected - 1) % 3
            self._update_display()

    def action_move_down(self) -> None:
        if not self._feedback_mode:
            self._selected = (self._selected + 1) % 3
            self._update_display()

    def action_confirm(self) -> None:
        if self._feedback_mode:
            return
        if self._selected == 0:
            self.result = ("yes", "")
        elif self._selected == 1:
            self.result = ("always", "")
        else:
            self._feedback_mode = True
            self._update_display()

    def action_select_yes(self) -> None:
        if not self._feedback_mode:
            self.result = ("yes", "")

    def action_select_always(self) -> None:
        if not self._feedback_mode:
            self.result = ("always", "")

    def action_select_no(self) -> None:
        if not self._feedback_mode:
            self._feedback_mode = True
            self._update_display()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "approval-feedback":
            self.result = ("no", event.value or "")


class ImageChip(Static, can_focus=True):
    """Minimal image indicator that can be removed with backspace."""

    BINDINGS = [
        Binding("backspace", "remove", "Remove", show=False),
        Binding("delete", "remove", "Remove", show=False),
        Binding("left", "nav_left", "Left", show=False),
        Binding("right", "nav_right", "Right", show=False),
        Binding("down", "nav_down", "Down", show=False),
    ]

    def __init__(self, name: str, index: int, **kwargs):
        super().__init__(**kwargs)
        self.image_name = name
        self.index = index

    def render(self) -> Text:
        # Truncate long names
        display_name = self.image_name
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
        if self.has_focus:
            return Text.from_markup(f"[bold #7dcfff]\\[{escape(display_name)}][/]")
        return Text.from_markup(f"[#7dcfff]\\[{escape(display_name)}][/]")

    def action_remove(self) -> None:
        self.post_message(self.Removed(self.index))

    def action_nav_left(self) -> None:
        self.post_message(self.Navigate(self.index, "left"))

    def action_nav_right(self) -> None:
        self.post_message(self.Navigate(self.index, "right"))

    def action_nav_down(self) -> None:
        self.post_message(self.Navigate(self.index, "down"))

    class Removed(Message):
        """Posted when chip is removed."""

        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    class Navigate(Message):
        """Posted for chip navigation."""

        def __init__(self, index: int, direction: str) -> None:
            self.index = index
            self.direction = direction
            super().__init__()


class CommandStatus(Static):
    """Shows running command with pulsating dot and optional output preview."""

    MAX_OUTPUT_LINES = 3
    MAX_LINE_LENGTH = 80

    def __init__(self, command: str, status: str | None = None, output: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.command = command
        self._pulse = 0
        self._status: str | None = status
        self._output: str | None = output
        self._timer = None

    def on_mount(self) -> None:
        # Only start pulsing timer if not already completed
        if self._status is None:
            self._timer = self.set_interval(0.15, self._tick)

    def _tick(self) -> None:
        self._pulse = (self._pulse + 1) % 6
        self.refresh()

    def set_status(self, status: str, output: str | None = None) -> None:
        self._status = status
        self._output = output
        # Stop the pulsing timer
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.refresh()

    def render(self) -> Text:
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

        result = f"{dot} [dim]$ {escape(self.command)}[/]{hint}"

        # Add output preview if available
        if self._output and self._status in ("success", "error"):
            lines = [l for l in self._output.strip().split("\n") if l.strip()]
            if lines:
                preview_lines = []
                for line in lines[: self.MAX_OUTPUT_LINES]:
                    if len(line) > self.MAX_LINE_LENGTH:
                        line = line[: self.MAX_LINE_LENGTH - 3] + "..."
                    preview_lines.append(f"  [dim #7dcfff]→[/] [#a9b1d6]{escape(line)}[/]")
                if len(lines) > self.MAX_OUTPUT_LINES:
                    preview_lines.append(f"  [dim]... +{len(lines) - self.MAX_OUTPUT_LINES} more lines[/]")
                result += "\n" + "\n".join(preview_lines)

        return Text.from_markup(result)


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
        self._generating = False
        self._cancel_requested = False
        self.working_dir: Path = Path.cwd()

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
            with Horizontal(id=f"{self.panel_id}-chips-row", classes="panel-chips-row"):
                yield Horizontal(id=f"{self.panel_id}-chips", classes="panel-chips")
                yield Static("Ctrl+C to quit", id=f"{self.panel_id}-quit-hint", classes="panel-quit-hint")
            yield MultilineInput(
                placeholder="Type... (/ for commands)", id=f"{self.panel_id}-prompt", classes="panel-prompt"
            )
            yield Static("", id=f"{self.panel_id}-hint", classes="panel-hint")

    def on_mount(self) -> None:
        self.call_after_refresh(self._show_welcome)

    def _show_welcome(self, force_compact: bool = False) -> None:
        chat = self.query_one(f"#{self.panel_id}-chat", Vertical)
        use_big = self.size.width >= 70 and not force_compact
        art = WELCOME_ART if use_big else WELCOME_ART_COMPACT

        # Get banner and tip from bulletin system
        manager = get_bulletin_manager()
        manager.load_sync("banners")
        manager.load_sync("tips")
        banners = manager.get_active("banners")
        tips = manager.get_active("tips")

        banner_line = banners[0].content if banners else ""
        tip_line = random.choice(tips).content if tips else ""
        tip_text = f"\nTip: {tip_line}" if tip_line else ""
        welcome = f"""{art}
[dim]{APP_CREDIT}[/]
[dim]v{APP_VERSION}[/]

{banner_line}

[#565f89][bold]/[/] for commands · [bold]Ctrl+S[/] for sessions{tip_text}[/]"""
        chat.remove_children()
        chat.mount(Static(welcome, classes="panel-welcome"))

    def on_click(self, event: events.Click) -> None:
        """Click to focus this panel."""
        if not self._is_active:
            self.post_message(self.Clicked(self))

    class Clicked(Message):
        """Posted when panel is clicked."""

        def __init__(self, panel: "ChatPanel") -> None:
            super().__init__()
            self.panel = panel

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

    def get_chips_container(self) -> Horizontal:
        return self.query_one(f"#{self.panel_id}-chips", Horizontal)

    def refresh_image_chips(self) -> None:
        """Update image chips display."""
        container = self.get_chips_container()
        container.remove_children()
        base_id = int(time.time() * 1000)
        for i, img in enumerate(self.pending_images):
            container.mount(ImageChip(img.name, i, id=f"{self.panel_id}-chip-{base_id}-{i}"))

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
        """Show ephemeral info (replaces previous info, not sent to model)."""
        chat = self.get_chat_container()
        # Remove previous info widgets (they have no id, just class check)
        for widget in chat.query(".info-text"):
            widget.remove()
        chat.mount(Static(f"[dim]{text}[/]", classes="info-text"))
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
        # Restore working directory from session (or reset to cwd)
        saved_dir = get_session_working_dir(session_id)
        self.working_dir = Path(saved_dir) if saved_dir else Path.cwd()
        chat = self.get_chat_container()
        chat.remove_children()
        base_id = int(time.time() * 1000)
        widget_id = 0
        for msg in self.messages:
            if msg["role"] not in ("user", "assistant"):
                continue

            # Handle new segment-based format for assistant messages
            if msg["role"] == "assistant" and "segments" in msg:
                for seg in msg["segments"]:
                    widget_id += 1
                    if seg.get("type") == "tool":
                        widget = CommandStatus(
                            seg.get("command", ""),
                            status=seg.get("status", "success"),
                            output=seg.get("output"),
                            id=f"loaded-{base_id}-{widget_id}",
                        )
                        chat.mount(widget)
                    elif seg.get("type") == "text":
                        content = seg.get("content", "")
                        if content:
                            # Match StreamingText color and spacing
                            chat.mount(
                                Static(
                                    Text.from_markup(f"[#c0caf5]{escape(content)}[/]"),
                                    id=f"loaded-{base_id}-{widget_id}",
                                    classes="loaded-text",
                                )
                            )
                continue

            # Handle legacy format (content + tool_calls)
            if msg["role"] == "assistant":
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    widget_id += 1
                    widget = CommandStatus(
                        tc.get("command", ""),
                        status=tc.get("status", "success"),
                        output=tc.get("output"),
                        id=f"loaded-{base_id}-{widget_id}",
                    )
                    chat.mount(widget)

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
