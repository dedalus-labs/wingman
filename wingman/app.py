"""Main Wingman application."""

import asyncio
import re
import time
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static, Tree

from dedalus_labs import AsyncDedalus, DedalusRunner

from .checkpoints import get_checkpoint_manager, set_current_session
from .config import (
    APP_CREDIT,
    APP_NAME,
    APP_VERSION,
    COMMANDS,
    MARKETPLACE_SERVERS,
    MODELS,
    fetch_marketplace_servers,
    get_working_dir,
    load_api_key,
    set_working_dir,
)
from .context import AUTO_COMPACT_THRESHOLD
from .export import export_session_json, export_session_markdown, import_session_from_file
from .images import CachedImage, cache_image_immediately, create_image_message_from_cache, is_image_path
from .memory import clear_memory, load_memory, append_memory
from .sessions import get_session, load_sessions, rename_session, save_session
from .tools import (
    CODING_SYSTEM_PROMPT,
    FILE_TOOLS,
    add_text_segment,
    clear_segments,
    get_background_processes,
    get_pending_edit,
    get_segments,
    list_files,
    list_processes,
    request_background,
    set_app_instance,
    stop_process,
)
from .ui import APIKeyScreen, ChatPanel, CommandStatus, DiffModal, ImageChip, InputModal, SelectionModal, StreamingText, Thinking, ToolApproval


class WingmanApp(App):
    """Wingman - Your copilot for the terminal"""

    TITLE = "Wingman"
    SUB_TITLE = "Your copilot for the terminal"

    CSS = """
    Screen {
        background: #1a1b26;
    }

    /* Sidebar */
    #sidebar {
        width: 26;
        height: 100%;
        background: #1a1b26;
        border: solid #3b3d4d;
        border-title-color: #a9b1d6;
        border-title-style: bold;
    }

    #sidebar Tree {
        padding: 1;
        background: transparent;
    }

    /* Main area */
    #main {
        height: 100%;
    }

    /* Chat panel */
    #chat-panel {
        height: 1fr;
        background: #1a1b26;
        border: solid #3b3d4d;
        border-title-color: #a9b1d6;
        border-title-style: bold;
    }

    #chat {
        padding: 1 2;
        height: auto;
    }

    /* Welcome message - centered */
    #welcome {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        padding: 4 2;
    }

    /* Hide scrollbar by default */
    #chat-panel {
        scrollbar-size: 0 0;
    }

    #chat-panel:focus-within {
        scrollbar-size: 1 1;
    }

    /* Clean message styling - no blocks */
    ChatMessage {
        height: auto;
        margin-bottom: 1;
    }

    Thinking {
        height: auto;
        margin: 1 0;
    }

    CommandStatus {
        height: auto;
        margin: 1 0;
    }

    StreamingText {
        height: auto;
        margin: 1 0;
    }

    .loaded-text {
        height: auto;
        margin: 1 0;
    }

    ToolApproval {
        height: auto;
        margin: 0 0 1 0;
        padding: 1;
        background: #16161e;
        border: solid #3b3d4d;
    }

    ToolApproval:focus {
        border: solid #7aa2f7;
    }

    /* Input area */
    #input-panel {
        height: auto;
        min-height: 4;
        max-height: 10;
        background: #1a1b26;
        border: solid #3b3d4d;
        border-title-color: #a9b1d6;
        border-title-style: bold;
        padding: 1;
    }

    #prompt {
        background: #24283b;
        border: none;
    }

    #cmd-hint {
        height: auto;
        color: #565f89;
        padding: 0 1;
    }

    /* Status bar */
    #status {
        height: 1;
        dock: bottom;
        background: #16161e;
        color: #565f89;
        padding: 0 2;
    }

    /* Split panels container */
    #panels-container {
        height: 1fr;
    }

    /* Individual chat panel */
    ChatPanel {
        width: 1fr;
        height: 100%;
        border: solid #3b3d4d;
        background: #1a1b26;
    }

    ChatPanel.active-panel {
        border: solid #7aa2f7;
    }

    .panel-scroll {
        height: 1fr;
        scrollbar-size: 0 0;
    }

    .panel-scroll:focus-within {
        scrollbar-size: 1 1;
    }

    .panel-chat {
        padding: 1 2;
        height: auto;
    }

    .panel-welcome {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        padding: 2 1;
    }

    .panel-input {
        height: auto;
        min-height: 3;
        max-height: 8;
        padding: 0 1 1 1;
    }

    .panel-prompt {
        background: #24283b;
        border: none;
    }

    .panel-hint {
        height: auto;
        color: #565f89;
        padding: 0 1;
    }

    .panel-chips {
        height: auto;
        width: 100%;
    }

    ImageChip {
        height: 1;
        width: auto;
        margin: 0 1 0 0;
    }

    """

    BINDINGS = [
        Binding("ctrl+n", "new_session", "New Chat"),
        Binding("ctrl+o", "open_session", "Open"),
        Binding("ctrl+s", "toggle_sidebar", "Sidebar"),
        Binding("ctrl+m", "select_model", "Model"),
        Binding("ctrl+g", "add_mcp", "MCP"),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+b", "background", "Background"),
        Binding("ctrl+z", "undo", "Undo"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("f1", "help", "Help"),
        # Split panel controls
        Binding("ctrl+\\", "split_panel", "Split"),
        Binding("ctrl+w", "close_panel", "Close Panel"),
        Binding("ctrl+left", "prev_panel", "Prev Panel", show=False),
        Binding("ctrl+right", "next_panel", "Next Panel", show=False),
        Binding("ctrl+1", "goto_panel_1", "Panel 1", show=False),
        Binding("ctrl+2", "goto_panel_2", "Panel 2", show=False),
        Binding("ctrl+3", "goto_panel_3", "Panel 3", show=False),
        Binding("ctrl+4", "goto_panel_4", "Panel 4", show=False),
    ]

    def __init__(self):
        super().__init__()
        set_app_instance(self)
        self.client: AsyncDedalus | None = None
        self.runner: DedalusRunner | None = None
        self.model = MODELS[0]
        self.coding_mode: bool = True
        # Panel management
        self.panels: list[ChatPanel] = []
        self.active_panel_idx: int = 0

    def _init_client(self, api_key: str) -> None:
        """Initialize Dedalus client with API key."""
        self.client = AsyncDedalus(api_key=api_key)
        self.runner = DedalusRunner(self.client)

    @property
    def active_panel(self) -> ChatPanel | None:
        """Get the currently active panel."""
        if not self.panels:
            return None
        return self.panels[self.active_panel_idx]

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="sidebar") as sidebar:
                sidebar.border_title = "Sessions"
                yield Tree("Chats", id="sessions")
            with Vertical(id="main"):
                with Horizontal(id="panels-container"):
                    panel = ChatPanel()
                    self.panels.append(panel)
                    yield panel
        yield Static(id="status")

    def on_mount(self) -> None:
        self._refresh_sessions()
        self._update_status()
        self.query_one("#sidebar").display = False
        # Set first panel as active
        if self.panels:
            self.panels[0].set_active(True)
        # Check for API key
        api_key = load_api_key()
        if api_key:
            self._init_client(api_key)
        else:
            self.push_screen(APIKeyScreen(), self._on_api_key_entered)
        # Fetch marketplace servers in background
        self._init_dynamic_data()

    @work(thread=False)
    async def _init_dynamic_data(self) -> None:
        """Fetch marketplace servers from API."""
        servers = await fetch_marketplace_servers()
        if servers:
            MARKETPLACE_SERVERS.clear()
            MARKETPLACE_SERVERS.extend(servers)

    def _on_api_key_entered(self, api_key: str | None) -> None:
        """Callback when API key is entered."""
        if api_key:
            self._init_client(api_key)
            if self.active_panel:
                self.active_panel.get_input().focus()

    def _update_status(self) -> None:
        model_short = self.model.split("/")[-1]
        panel = self.active_panel
        mcp_count = len(panel.mcp_servers) if panel else 0
        mcp_text = f" │ MCP: {mcp_count}" if mcp_count else ""
        session_text = panel.session_id if panel and panel.session_id else "New Chat"

        # Coding mode indicator
        code_text = " │ [#9ece6a]CODE[/]" if self.coding_mode else ""

        # Pending images indicator
        img_count = len(panel.pending_images) if panel else 0
        img_text = f" │ [#7dcfff]{img_count} image{'s' if img_count != 1 else ''}[/]" if img_count else ""

        # Context remaining indicator
        if panel:
            remaining = 1.0 - panel.context.usage_percent
        else:
            remaining = 1.0
        if remaining <= (1.0 - AUTO_COMPACT_THRESHOLD):
            ctx_color = "#f7768e"
        elif remaining <= 0.4:
            ctx_color = "#e0af68"
        else:
            ctx_color = "#565f89"
        ctx_text = f" │ [bold {ctx_color}]Context: {int(remaining * 100)}%[/]"

        # Memory indicator
        memory_text = " │ [#bb9af7]MEM[/]" if load_memory() else ""

        # Panel indicator
        panel_count = len(self.panels)
        panel_text = f" │ Panel {self.active_panel_idx + 1}/{panel_count}" if panel_count > 1 else ""

        status = f"{session_text} │ {model_short}{code_text}{memory_text}{img_text}{mcp_text}{ctx_text}{panel_text}"
        self.query_one("#status", Static).update(Text.from_markup(status))

    def _refresh_sessions(self) -> None:
        tree = self.query_one("#sessions", Tree)
        tree.clear()
        tree.root.expand()
        sessions = load_sessions()
        for name in sorted(sessions.keys()):
            tree.root.add_leaf(name)

    def _load_session(self, session_id: str) -> None:
        """Load a session into the active panel."""
        if self.active_panel:
            self.active_panel.load_session(session_id)
            self._update_status()

    def _show_info(self, text: str) -> None:
        """Show info in the active panel."""
        if self.active_panel:
            self.active_panel.show_info(text)

    def _show_context_info(self) -> None:
        """Display detailed context usage information."""
        if not self.active_panel:
            return
        ctx = self.active_panel.context
        used = ctx.total_tokens
        limit = ctx.context_limit
        remaining_pct = (1.0 - ctx.usage_percent) * 100
        remaining_tokens = ctx.tokens_remaining
        msg_count = len(ctx.messages)

        info = f"""[bold #7aa2f7]Context Status[/]
  Model: {ctx.model}
  Remaining: [bold]{remaining_pct:.1f}%[/] ({remaining_tokens:,} tokens)
  Used: {used:,} / {limit:,} tokens
  Messages: {msg_count}

  {"[#f7768e]LOW - consider /compact[/]" if ctx.needs_compacting else "[#9ece6a]OK[/]"}"""
        self._show_info(info)

    @work(thread=False)
    async def _do_compact(self) -> None:
        """Manually trigger context compaction."""
        panel = self.active_panel
        if not panel:
            return
        if self.client is None:
            self._show_info("[#f7768e]Please enter your API key first.[/]")
            return
        if len(panel.context.messages) < 4:
            self._show_info("Not enough messages to compact")
            return

        chat = panel.get_chat_container()
        thinking = Thinking(id="compact-thinking")
        chat.mount(thinking)
        self._show_info("Compacting context...")

        try:
            result = await panel.context.compact(self.client)
            thinking.remove()
            self._show_info(f"[#9ece6a]{result}[/]")
            self._update_status()
            if panel.session_id:
                save_session(panel.session_id, panel.context.messages)
        except Exception as e:
            thinking.remove()
            self._show_info(f"[#f7768e]Compact failed: {e}[/]")

    async def _check_auto_compact(self, panel: ChatPanel) -> None:
        """Auto-compact if context is running low."""
        if self.client is None:
            return
        if panel.context.needs_compacting:
            remaining = int((1.0 - panel.context.usage_percent) * 100)
            panel.show_info(f"[#e0af68]Context low ({remaining}% remaining) - auto-compacting...[/]")
            try:
                result = await panel.context.compact(self.client)
                panel.show_info(f"[#9ece6a]{result}[/]")
                self._update_status()
            except Exception as e:
                panel.show_info(f"[#f7768e]Auto-compact failed: {e}[/]")

    def on_descendant_focus(self, event) -> None:
        """Set panel as active when any of its descendants receives focus."""
        for i, panel in enumerate(self.panels):
            if panel in event.widget.ancestors_with_self:
                if i != self.active_panel_idx:
                    self._set_active_panel(i)
                break

    @on(ImageChip.Removed)
    def on_image_chip_removed(self, event: ImageChip.Removed) -> None:
        """Remove an image when its chip is deleted."""
        panel = self.active_panel
        if panel and 0 <= event.index < len(panel.pending_images):
            panel.pending_images.pop(event.index)
            panel.refresh_image_chips()
            self._update_status()
            # Focus next chip or input after mount completes
            if panel.pending_images:
                new_idx = min(event.index, len(panel.pending_images) - 1)
                def focus_chip():
                    chips = list(panel.get_chips_container().query(ImageChip))
                    if chips and new_idx < len(chips):
                        chips[new_idx].focus()
                self.call_after_refresh(focus_chip)
            else:
                panel.get_hint().update("")
                panel.get_input().focus()

    @on(ImageChip.Navigate)
    def on_image_chip_navigate(self, event: ImageChip.Navigate) -> None:
        """Handle chip navigation."""
        panel = self.active_panel
        if not panel:
            return
        chips = list(panel.get_chips_container().query(ImageChip))
        if event.direction == "down":
            panel.get_input().focus()
        elif event.direction == "left" and event.index > 0:
            chips[event.index - 1].focus()
        elif event.direction == "right" and event.index < len(chips) - 1:
            chips[event.index + 1].focus()

    def on_key(self, event) -> None:
        """Handle arrow navigation for image chips."""
        panel = self.active_panel
        if not panel:
            return
        focused = self.focused

        # Up from input -> last chip
        if event.key == "up" and panel.pending_images:
            if focused and isinstance(focused, Input) and "panel-prompt" in focused.classes:
                chips = list(panel.get_chips_container().query(ImageChip))
                if chips:
                    event.prevent_default()
                    chips[-1].focus()

        # Navigation when chip is focused
        elif isinstance(focused, ImageChip):
            chips = list(panel.get_chips_container().query(ImageChip))
            try:
                idx = chips.index(focused)
            except ValueError:
                return

            if event.key == "down":
                event.prevent_default()
                panel.get_input().focus()
            elif event.key == "left" and idx > 0:
                event.prevent_default()
                chips[idx - 1].focus()
            elif event.key == "right" and idx < len(chips) - 1:
                event.prevent_default()
                chips[idx + 1].focus()

    @on(Input.Changed, ".panel-prompt")
    def on_input_changed(self, event: Input.Changed) -> None:
        """Show command hints when typing / and auto-detect image paths."""
        panel = None
        for ancestor in event.input.ancestors_with_self:
            if isinstance(ancestor, ChatPanel):
                panel = ancestor
                break
        if not panel:
            return
        hint = panel.get_hint()
        text = event.value

        # Auto-detect image paths (drag-and-drop)
        if text and any(text.strip().strip("'\"").lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
            image_path = is_image_path(text)
            if image_path:
                # Prevent duplicate adds from rapid-fire input events
                if any(img.name == image_path.name for img in panel.pending_images):
                    event.input.clear()
                    return
                cached = cache_image_immediately(image_path)
                if cached:
                    event.input.clear()
                    panel.pending_images.append(cached)
                    panel.refresh_image_chips()
                    panel.get_hint().update("[dim]↑ to select images · backspace to remove[/]")
                    self._update_status()
                    return

        if text.startswith("/"):
            search = text[1:].lower()
            matches = [f"[#7aa2f7]{cmd}[/]" for cmd, desc in COMMANDS
                       if search in cmd.lower() or search in desc.lower()]
            hint.update("  ".join(matches) if matches else "")
        elif panel.pending_images:
            hint.update("[dim]↑ to select images · backspace to remove[/]")
        else:
            hint.update("")

    @on(Input.Submitted, ".panel-prompt")
    def on_submit(self, event: Input.Submitted) -> None:
        panel = None
        for p in self.panels:
            if p.panel_id in event.input.id:
                panel = p
                break
        if not panel:
            return

        # Activate this panel if it's not active
        if panel != self.active_panel:
            self._set_active_panel(self.panels.index(panel))

        text = event.value.strip()

        if not text and not panel.pending_images:
            return

        event.input.clear()
        panel.get_hint().update("")

        if text.startswith("/"):
            self._handle_command(text)
            return

        # Remove welcome message if present
        try:
            for child in panel.get_chat_container().children:
                if "panel-welcome" in child.classes:
                    child.remove()
                    break
        except Exception:
            pass

        # Create new session if none exists
        if not panel.session_id:
            panel.session_id = f"chat-{int(time.time())}"
            save_session(panel.session_id, [])
            self._refresh_sessions()
            self._update_status()

        # Handle images in message
        images_to_send = panel.pending_images.copy()
        panel.pending_images = []
        panel.refresh_image_chips()  # Clear chips display

        if images_to_send:
            panel.add_image_message("user", text, images_to_send)
        else:
            panel.add_message("user", text)

        chat = panel.get_chat_container()
        thinking = Thinking(id="thinking")
        chat.mount(thinking)
        panel.get_scroll_container().scroll_end(animate=False)

        self._send_message(panel, text, thinking, images_to_send)

    @work(thread=False)
    async def _send_message(self, panel: ChatPanel, text: str, thinking: Thinking, images: list[CachedImage] | None = None) -> None:
        if self.runner is None:
            thinking.remove()
            panel.add_message("assistant", "Please enter your API key first.")
            self.push_screen(APIKeyScreen(), self._on_api_key_entered)
            return
        try:
            # Build messages with system prompt if in coding mode
            # Convert segment-based messages to content format for the model
            messages = []
            for msg in panel.messages:
                if msg.get("segments"):
                    # Extract text content from segments
                    text_parts = [s["content"] for s in msg["segments"] if s.get("type") == "text"]
                    messages.append({"role": msg["role"], "content": "".join(text_parts)})
                else:
                    messages.append(msg.copy())

            # Replace the last user message with image version if images were attached
            if images and messages and messages[-1].get("role") == "user":
                messages[-1] = create_image_message_from_cache(text, images)

            if self.coding_mode:
                system_content = CODING_SYSTEM_PROMPT.format(cwd=get_working_dir())
                # Include project memory if available
                memory = load_memory()
                if memory:
                    system_content += f"\n\n## Project Memory\n{memory}"
                system_msg = {
                    "role": "system",
                    "content": system_content
                }
                messages = [system_msg] + messages

            kwargs = {
                "messages": messages,
                "model": self.model,
                "max_steps": 10,
                "stream": True,
            }
            if panel.mcp_servers:
                kwargs["mcp_servers"] = panel.mcp_servers
            if self.coding_mode:
                kwargs["tools"] = FILE_TOOLS

            # Set session context for checkpoint tracking
            set_current_session(panel.session_id)
            clear_segments()  # Clear segment tracking for new response
            chat = panel.get_chat_container()

            streaming_widget = None
            widget_id = int(time.time() * 1000)  # Unique base ID per message

            try:
                stream = self.runner.run(**kwargs)
                async for chunk in stream:
                    if hasattr(chunk, "choices") and chunk.choices:
                        delta = chunk.choices[0].delta

                        # Tool call detected - finalize current text segment
                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            if streaming_widget is not None:
                                streaming_widget.mark_complete()
                                streaming_widget = None

                        # Stream text content
                        if hasattr(delta, "content") and delta.content:
                            if streaming_widget is None:
                                widget_id += 1
                                streaming_widget = StreamingText(id=f"streaming-{widget_id}")
                                chat.mount(streaming_widget, before=thinking)
                            add_text_segment(delta.content)  # Track text segment
                            streaming_widget.append_text(delta.content)
                            panel.get_scroll_container().scroll_end(animate=False)
                            await asyncio.sleep(0)
            finally:
                set_current_session(None)

            if streaming_widget is not None:
                streaming_widget.mark_complete()

            try:
                thinking.remove()
            except Exception:
                pass

            segments = get_segments()
            if segments:
                panel.messages.append({"role": "assistant", "segments": segments})
                save_session(panel.session_id, panel.messages)
            else:
                # Stream ended with no content
                self._show_info("[#e0af68]Response ended with no content[/]")

            self._update_status()
            await self._check_auto_compact(panel)

        except asyncio.TimeoutError:
            try:
                thinking.remove()
            except Exception:
                pass
            for sw in self.query(StreamingText):
                try:
                    sw.remove()
                except Exception:
                    pass
            self._show_info("[#f7768e]Request timed out[/]")

        except Exception as e:
            # Clean up thinking spinner
            try:
                thinking.remove()
            except Exception:
                pass
            # Clean up any streaming widgets
            for sw in self.query(StreamingText):
                try:
                    sw.remove()
                except Exception:
                    pass
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                self._show_info("[#f7768e]Request timed out[/]")
            else:
                panel.add_message("assistant", f"[#f7768e]Error: {e}[/]")

    def show_diff_approval(self) -> None:
        """Show diff modal for pending edit approval. Called from tool thread."""
        pending = get_pending_edit()
        if pending is None:
            return
        self._show_diff_modal(
            pending["path"],
            pending["old_string"],
            pending["new_string"],
        )

    async def request_tool_approval(self, tool_name: str, command: str) -> str:
        """Request approval for a tool. Returns 'yes', 'always', or 'no'."""
        panel = self.active_panel
        if not panel:
            return "yes"
        chat = panel.get_chat_container()
        widget = ToolApproval(tool_name, command, id="tool-approval")
        # Mount before thinking spinner so it stays at bottom
        try:
            thinking = self.query_one("#thinking", Thinking)
            chat.mount(widget, before=thinking)
        except Exception:
            chat.mount(widget)
        panel.get_scroll_container().scroll_end(animate=False)
        while widget.result is None:
            await asyncio.sleep(0.05)
        result = widget.result
        widget.remove()
        return result

    def action_background(self) -> None:
        """Request backgrounding of current command (Ctrl+B)."""
        request_background()

    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar visibility."""
        sidebar = self.query_one("#sidebar")
        sidebar.display = not sidebar.display

    def _set_active_panel(self, idx: int) -> None:
        """Set the active panel by index."""
        if idx < 0 or idx >= len(self.panels):
            return
        # Deactivate current
        if self.active_panel:
            self.active_panel.set_active(False)
        # Activate new
        self.active_panel_idx = idx
        self.panels[idx].set_active(True)
        self._update_status()

    def action_split_panel(self) -> None:
        """Create a new panel (Ctrl+\\)."""
        if len(self.panels) >= 4:
            self._show_info("Maximum 4 panels allowed")
            return
        container = self.query_one("#panels-container", Horizontal)
        panel = ChatPanel()
        self.panels.append(panel)
        container.mount(panel)
        # Refresh welcome art on existing panels after layout recalculates
        self.call_after_refresh(self._refresh_welcome_art)
        # Activate the new panel
        self._set_active_panel(len(self.panels) - 1)
        self._update_status()

    def _refresh_welcome_art(self) -> None:
        """Re-render welcome art on panels that have it (after resize)."""
        for p in self.panels:
            try:
                p.query_one(".panel-welcome")
                p._show_welcome()
            except Exception:
                pass

    def on_resize(self, event) -> None:
        """Handle terminal resize - refresh welcome art."""
        self.call_after_refresh(self._refresh_welcome_art)

    def action_close_panel(self) -> None:
        """Close the active panel (Ctrl+W)."""
        if len(self.panels) <= 1:
            self._show_info("Cannot close the last panel")
            return
        panel = self.active_panel
        if not panel:
            return
        idx = self.active_panel_idx
        # Update index BEFORE removing to avoid out of bounds
        new_idx = idx - 1 if idx > 0 else 0
        self.active_panel_idx = new_idx
        # Now remove the panel
        panel.remove()
        self.panels.remove(panel)
        # Refresh welcome art on remaining panels (may have more space now)
        self.call_after_refresh(self._refresh_welcome_art)
        # Activate the new panel
        self.panels[new_idx].set_active(True)
        self._update_status()

    def action_prev_panel(self) -> None:
        """Switch to previous panel (Ctrl+Left)."""
        if len(self.panels) <= 1:
            return
        new_idx = (self.active_panel_idx - 1) % len(self.panels)
        self._set_active_panel(new_idx)

    def action_next_panel(self) -> None:
        """Switch to next panel (Ctrl+Right)."""
        if len(self.panels) <= 1:
            return
        new_idx = (self.active_panel_idx + 1) % len(self.panels)
        self._set_active_panel(new_idx)

    def action_goto_panel_1(self) -> None:
        if len(self.panels) >= 1:
            self._set_active_panel(0)

    def action_goto_panel_2(self) -> None:
        if len(self.panels) >= 2:
            self._set_active_panel(1)

    def action_goto_panel_3(self) -> None:
        if len(self.panels) >= 3:
            self._set_active_panel(2)

    def action_goto_panel_4(self) -> None:
        if len(self.panels) >= 4:
            self._set_active_panel(3)

    def _mount_command_status(self, command: str, widget_id: str) -> None:
        """Mount command status widget in active panel, before Thinking spinner."""
        panel = self.active_panel
        if not panel:
            return
        chat = panel.get_chat_container()
        widget = CommandStatus(command, id=widget_id)
        # Mount before thinking spinner so it stays at bottom
        try:
            thinking = self.query_one("#thinking", Thinking)
            chat.mount(widget, before=thinking)
        except Exception:
            chat.mount(widget)
        panel.get_scroll_container().scroll_end(animate=False)

    def _update_command_status(self, widget_id: str, status: str, output: str | None = None) -> None:
        """Update command status widget with final status and optional output."""
        try:
            widget = self.query_one(f"#{widget_id}", CommandStatus)
            widget.set_status(status, output)
        except Exception:
            pass

    @work
    async def _show_diff_modal(self, path: str, old_string: str, new_string: str) -> None:
        """Display diff modal and handle approval."""
        from .tools import set_edit_result
        result = await self.push_screen_wait(DiffModal(path, old_string, new_string))
        set_edit_result(result)

    def _cmd_rename(self, arg: str) -> None:
        panel = self.active_panel
        if not panel or not panel.session_id:
            self._show_info("No active session to rename")
        elif arg:
            if rename_session(panel.session_id, arg):
                old_name = panel.session_id
                panel.session_id = arg
                self._refresh_sessions()
                self._update_status()
                self._show_info(f"Renamed '{old_name}' → '{arg}'")
            else:
                self._show_info(f"Could not rename: '{arg}' may already exist")
        else:
            self._show_info("Usage: /rename <new-name>")

    def _cmd_mcp(self, arg: str) -> None:
        panel = self.active_panel
        if not panel:
            return
        if not arg:
            self.action_add_mcp()
        elif arg == "clear":
            panel.mcp_servers = []
            self._show_info("Cleared all MCP servers")
            self._update_status()
        else:
            panel.mcp_servers.append(arg)
            self._show_info(f"Added MCP server: {arg}")
            self._update_status()

    def _cmd_code(self, arg: str) -> None:
        self.coding_mode = not self.coding_mode
        status = "[#9ece6a]ON[/]" if self.coding_mode else "[#f7768e]OFF[/]"
        self._show_info(f"Coding mode: {status}")
        self._update_status()

    def _cmd_cd(self, arg: str) -> None:
        if not arg:
            self._show_info(f"Working directory: {get_working_dir()}")
        else:
            new_dir = Path(arg).expanduser().resolve()
            if new_dir.is_dir():
                set_working_dir(new_dir)
                self._show_info(f"Changed to: {get_working_dir()}")
                self._update_status()
            else:
                self._show_info(f"Not a directory: {arg}")

    def _cmd_history(self, arg: str) -> None:
        panel = self.active_panel
        cp_manager = get_checkpoint_manager()
        session_id = panel.session_id if panel else None
        checkpoints = cp_manager.list_recent(15, session_id=session_id)
        if not checkpoints:
            self._show_info("No checkpoints for this session. Checkpoints are created automatically before file edits.")
        else:
            lines = ["[bold #7aa2f7]Checkpoints[/] (use /rollback <id> to restore)\n"]
            for cp in checkpoints:
                ts = time.strftime("%H:%M:%S", time.localtime(cp.timestamp))
                files = ", ".join(Path(f).name for f in cp.files.keys())
                lines.append(f"  [#9ece6a]{cp.id}[/] [{ts}] {cp.description}")
                lines.append(f"    [dim]{files}[/]")
            self._show_info("\n".join(lines))

    def _cmd_rollback(self, arg: str) -> None:
        if not arg:
            self._show_info("Usage: /rollback <checkpoint_id>\nUse /history to see available checkpoints.")
            return
        panel = self.active_panel
        cp_manager = get_checkpoint_manager()
        cp = cp_manager.get(arg)
        session_id = panel.session_id if panel else None
        if cp and cp.session_id and cp.session_id != session_id:
            self._show_info(f"[#e0af68]Checkpoint {arg} belongs to a different session.[/]")
            return
        restored = cp_manager.restore(arg)
        if restored:
            self._show_info(f"[#9ece6a]Restored {len(restored)} file(s):[/]\n" + "\n".join(f"  • {f}" for f in restored))
        else:
            self._show_info(f"[#f7768e]Checkpoint not found: {arg}[/]")

    def _cmd_diff(self, arg: str) -> None:
        panel = self.active_panel
        cp_manager = get_checkpoint_manager()
        session_id = panel.session_id if panel else None
        if not arg:
            recent = cp_manager.list_recent(1, session_id=session_id)
            if recent:
                arg = recent[0].id
            else:
                self._show_info("No checkpoints available for this session. Use /diff <checkpoint_id>")
                return
        diffs = cp_manager.diff(arg)
        if not diffs:
            self._show_info(f"No changes since checkpoint {arg}")
        else:
            lines = [f"[bold #7aa2f7]Changes since {arg}[/]\n"]
            for fpath, diff_text in diffs.items():
                lines.append(f"[#e0af68]{Path(fpath).name}[/]")
                for line in diff_text.split("\n"):
                    if line.startswith("+") and not line.startswith("+++"):
                        lines.append(f"[#9ece6a]{line}[/]")
                    elif line.startswith("-") and not line.startswith("---"):
                        lines.append(f"[#f7768e]{line}[/]")
                    elif line.startswith("@@"):
                        lines.append(f"[#7aa2f7]{line}[/]")
                    else:
                        lines.append(f"[dim]{line}[/]")
            self._show_info("\n".join(lines))

    def _cmd_memory(self, arg: str) -> None:
        if not arg:
            memory = load_memory()
            if memory:
                self._show_info(f"[bold #7aa2f7]Project Memory[/]\n\n{memory}")
            else:
                self._show_info("[dim]No project memory set. Use /memory add <text> to add notes.[/]")
        elif arg == "clear":
            clear_memory()
            self._show_info("[#9ece6a]Project memory cleared[/]")
        elif arg.startswith("add "):
            text = arg[4:].strip()
            if text:
                append_memory(text)
                self._show_info(f"[#9ece6a]Added to memory:[/] {text[:50]}...")
            else:
                self._show_info("Usage: /memory add <text>")
        else:
            self._show_info("Usage: /memory, /memory add <text>, /memory clear")

    def _cmd_export(self, arg: str) -> None:
        panel = self.active_panel
        if not panel or not panel.messages:
            self._show_info("No messages to export")
            return
        session_name = panel.session_id or f"chat-{int(time.time())}"
        if arg == "json":
            content = export_session_json(panel.messages, session_name)
            filename = f"{session_name}.json"
        else:
            content = export_session_markdown(panel.messages, session_name)
            filename = f"{session_name}.md"
        export_path = get_working_dir() / filename
        export_path.write_text(content)
        self._show_info(f"[#9ece6a]Exported to:[/] {export_path}")

    def _cmd_import(self, arg: str) -> None:
        if not arg:
            self._show_info("Usage: /import <path>")
            return
        panel = self.active_panel
        import_path = Path(arg).expanduser()
        if not import_path.is_absolute():
            import_path = get_working_dir() / import_path
        messages = import_session_from_file(import_path)
        if messages and panel:
            count = 0
            for msg in messages:
                if msg["role"] in ("user", "assistant") and msg.get("content"):
                    content = msg["content"]
                    if isinstance(content, list):
                        content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
                    panel.messages.append({"role": msg["role"], "content": content})
                    count += 1
            self._update_status()
            self._show_info(f"[#9ece6a]Imported {count} messages as context[/]")
        else:
            self._show_info(f"[#f7768e]Could not import from:[/] {arg}")

    def _handle_command(self, cmd: str) -> None:
        parts = cmd[1:].split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        # Simple command dispatch
        simple_commands = {
            "new": lambda: self.action_new_session(),
            "split": lambda: self.action_split_panel(),
            "close": lambda: self.action_close_panel(),
            "model": lambda: self.action_select_model(),
            "compact": lambda: self._do_compact(),
            "context": lambda: self._show_context_info(),
            "key": lambda: self.push_screen(APIKeyScreen(), self._on_api_key_entered),
            "clear": lambda: self.action_clear_chat(),
            "help": lambda: self.action_help(),
            "quit": lambda: self.exit(),
            "ls": lambda: self._do_ls(arg or "*"),
            "ps": lambda: self._show_info(f"[bold #7aa2f7]Background Processes[/]\n{list_processes()}"),
            "processes": lambda: self._show_info(f"[bold #7aa2f7]Background Processes[/]\n{list_processes()}"),
            "kill": lambda: self._show_info(stop_process(arg) if arg else "Usage: /kill <process_id>"),
        }

        # Commands with complex logic
        complex_commands = {
            "rename": self._cmd_rename,
            "mcp": self._cmd_mcp,
            "code": self._cmd_code,
            "cd": self._cmd_cd,
            "history": self._cmd_history,
            "rollback": self._cmd_rollback,
            "diff": self._cmd_diff,
            "memory": self._cmd_memory,
            "export": self._cmd_export,
            "import": self._cmd_import,
        }

        if command in simple_commands:
            simple_commands[command]()
        elif command in complex_commands:
            complex_commands[command](arg)
        else:
            self._show_info(f"Unknown command: {command}")

    @work(thread=False)
    async def _do_ls(self, pattern: str) -> None:
        """List files asynchronously."""
        result = await list_files(pattern)
        self._show_info(f"[dim]{get_working_dir()}[/]\n{result}")

    @on(Tree.NodeSelected, "#sessions")
    def on_session_select(self, event: Tree.NodeSelected) -> None:
        if event.node.is_root:
            return
        self._load_session(str(event.node.label))

    def action_new_session(self) -> None:
        """Start a new chat in the active panel."""
        panel = self.active_panel
        if not panel:
            return
        panel.session_id = None
        panel.context.clear()
        panel._show_welcome()
        self._update_status()
        panel.get_input().focus()

    @work
    async def action_open_session(self) -> None:
        sessions = list(load_sessions().keys())
        if not sessions:
            self._show_info("No saved sessions")
            return
        result = await self.push_screen_wait(
            SelectionModal("Open Session", sessions)
        )
        if result:
            self._load_session(result)
            self._refresh_sessions()

    @work
    async def action_select_model(self) -> None:
        result = await self.push_screen_wait(
            SelectionModal("Select Model", MODELS)
        )
        if result:
            self.model = result
            # Sync all panels' context model
            for panel in self.panels:
                panel.context.model = result
            self._show_info(f"Model: {result}")
            self._update_status()

    @work
    async def action_add_mcp(self) -> None:
        panel = self.active_panel
        if not panel:
            return
        options = []
        if MARKETPLACE_SERVERS:
            for server in MARKETPLACE_SERVERS:
                slug = server.get('slug', '')
                title = server.get('title') or slug.split('/')[-1]
                options.append(f"{title} ({slug})")
        options.append("+ Custom URL")

        result = await self.push_screen_wait(
            SelectionModal("Add MCP Server", options)
        )
        if result:
            if result == "+ Custom URL":
                custom = await self.push_screen_wait(
                    InputModal("Add MCP Server", placeholder="Enter server URL or slug...")
                )
                if custom:
                    panel.mcp_servers.append(custom)
                    self._show_info(f"Added MCP server: {custom}")
                    self._update_status()
            else:
                match = re.search(r'\(([^)]+)\)$', result)
                if match:
                    slug = match.group(1)
                    panel.mcp_servers.append(slug)
                    self._show_info(f"Added MCP server: {slug}")
                    self._update_status()

    def action_clear_chat(self) -> None:
        """Clear chat in the active panel."""
        panel = self.active_panel
        if not panel:
            return
        panel.clear_chat()
        self._update_status()

    def action_undo(self) -> None:
        """Undo last file change by restoring most recent checkpoint for this session."""
        cp_manager = get_checkpoint_manager()
        panel = self.active_panel
        session_id = panel.session_id if panel else None
        recent = cp_manager.list_recent(1, session_id=session_id)
        if not recent:
            self._show_info("[#e0af68]No checkpoints available to undo in this session[/]")
            return
        checkpoint = recent[0]
        restored = cp_manager.restore(checkpoint.id)
        if restored:
            self._show_info(f"[#9ece6a]Restored {len(restored)} file(s) from {checkpoint.id}:[/]\n" + "\n".join(f"  • {f}" for f in restored))
        else:
            self._show_info("[#f7768e]Failed to restore checkpoint[/]")

    def action_help(self) -> None:
        bg_count = len(get_background_processes())
        cp_count = len(get_checkpoint_manager()._checkpoints)
        panel = self.active_panel
        img_count = len(panel.pending_images) if panel else 0
        panel_count = len(self.panels)
        help_text = f"""[bold #7aa2f7]{APP_NAME}[/] [dim]v{APP_VERSION} · {APP_CREDIT}[/]

[bold #a9b1d6]Session[/]
  [#7aa2f7]/new[/]            New session
  [#7aa2f7]/rename <name>[/]  Rename current chat
  [#7aa2f7]/clear[/]          Clear chat history

[bold #a9b1d6]Panels[/]
  [#7aa2f7]/split[/]          Split into new panel
  [#7aa2f7]/close[/]          Close current panel
  [#7aa2f7]Ctrl+\\[/]         Split panel
  [#7aa2f7]Ctrl+W[/]          Close panel
  [#7aa2f7]Ctrl+←/→[/]        Switch panels
  [#7aa2f7]Ctrl+1-4[/]        Jump to panel

[bold #a9b1d6]Coding[/]
  [#7aa2f7]/code[/]           Toggle coding mode
  [#7aa2f7]/cd <path>[/]      Set working directory
  [#7aa2f7]/ls[/]             List files
  [#7aa2f7]/ps[/]             List background processes
  [#7aa2f7]/kill <id>[/]      Stop a process

[bold #a9b1d6]Rollback[/]
  [#7aa2f7]/history[/]        List checkpoints
  [#7aa2f7]/rollback <id>[/]  Restore from checkpoint
  [#7aa2f7]/diff [id][/]      Show changes since checkpoint

[bold #a9b1d6]Memory[/]
  [#7aa2f7]/memory[/]         View project memory
  [#7aa2f7]/memory add[/]     Add note to memory
  [#7aa2f7]/memory clear[/]   Clear memory

[bold #a9b1d6]Export/Import[/]
  [#7aa2f7]/export[/]         Export session to markdown
  [#7aa2f7]/export json[/]    Export as JSON
  [#7aa2f7]/import <path>[/]  Import from file

[bold #a9b1d6]Config[/]
  [#7aa2f7]/model[/]          Switch model
  [#7aa2f7]/context[/]        Show context usage

[bold #a9b1d6]Shortcuts[/]
  [#7aa2f7]Ctrl+Z[/]  Undo (restore last checkpoint)
  [#7aa2f7]Ctrl+B[/]  Background running command

[dim]Working dir: {get_working_dir()}[/]
[dim]Panels: {panel_count} · Background: {bg_count} · Checkpoints: {cp_count} · Images: {img_count}[/]"""
        self._show_info(help_text)


def main():
    app = WingmanApp()
    app.run()


if __name__ == "__main__":
    main()
