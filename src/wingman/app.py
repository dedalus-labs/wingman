"""Main Wingman application."""

import asyncio
import re
import time
import webbrowser
from pathlib import Path

from dedalus_labs import AsyncDedalus, DedalusRunner
from rich.markup import escape
from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static, Tree

from .checkpoints import get_checkpoint_manager, set_current_session
from .command_completion import get_hint_candidates
from .config import (
    APP_CREDIT,
    APP_NAME,
    APP_VERSION,
    MARKETPLACE_SERVERS,
    MODELS,
    fetch_marketplace_servers,
    load_api_key,
    load_instructions,
)
from .context import AUTO_COMPACT_THRESHOLD
from .export import export_session_json, export_session_markdown, import_session_from_file
from .images import CachedImage, cache_image_immediately, create_image_message_from_cache, is_image_path
from .memory import add_entry, clear_all, load_memory
from .sessions import delete_session, load_sessions, rename_session, save_session, save_session_working_dir
from .tools import (
    CODING_SYSTEM_PROMPT,
    add_text_segment,
    check_completed_processes,
    clear_segments,
    create_tools,
    get_background_processes,
    get_pending_edit,
    get_segments,
    list_processes,
    request_background,
    set_app_instance,
    stop_process,
)
from .ui import (
    APIKeyScreen,
    ChatPanel,
    CommandStatus,
    DiffModal,
    ImageChip,
    InputModal,
    SelectionModal,
    StreamingText,
    Thinking,
    ToolApproval,
)


class WingmanApp(App):
    """Wingman - Your copilot for the terminal"""

    TITLE = "Wingman"
    SUB_TITLE = "Your copilot for the terminal"

    CSS_PATH = "ui/app.tcss"

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
        Binding("ctrl+/", "help", "Help", show=False),
        Binding("ctrl+1", "goto_panel_1", "Panel 1", show=False),
        Binding("ctrl+2", "goto_panel_2", "Panel 2", show=False),
        Binding("ctrl+3", "goto_panel_3", "Panel 3", show=False),
        Binding("ctrl+4", "goto_panel_4", "Panel 4", show=False),
    ]

    def __init__(self):
        super().__init__()
        set_app_instance(self)
        self.scroll_sensitivity_y = 0.6
        self.client: AsyncDedalus | None = None
        self.runner: DedalusRunner | None = None
        self.model = MODELS[0]
        self.coding_mode: bool = True
        # Panel management
        self.panels: list[ChatPanel] = []
        self.active_panel_idx: int = 0
        self.last_ctrl_c: float | None = None

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
        # Monitor background processes for completion
        self.set_interval(2.0, self._check_background_processes)

    @work(thread=False)
    async def _init_dynamic_data(self) -> None:
        """Fetch marketplace servers from API."""
        servers = await fetch_marketplace_servers()
        if servers:
            MARKETPLACE_SERVERS.clear()
            MARKETPLACE_SERVERS.extend(servers)

    def _check_background_processes(self) -> None:
        """Periodic check for completed background processes."""
        completed = check_completed_processes()
        for panel_id, bg_id, exit_code, command in completed:
            # Shorten command for display
            cmd_short = command[:40] + "..." if len(command) > 40 else command
            if exit_code == 0:
                self.notify(f"[{bg_id}] completed: {cmd_short}", timeout=5.0)
            else:
                self.notify(f"[{bg_id}] failed (exit {exit_code}): {cmd_short}", timeout=5.0, severity="error")

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
        session_text = escape(panel.session_id) if panel and panel.session_id else "New Chat"

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
        memory_text = " │ [#bb9af7]MEM[/]" if load_memory().entries else ""

        # Generating indicator
        generating_text = " │ [#e0af68]Generating...[/]" if panel and panel._generating else ""

        # Panel indicator
        panel_count = len(self.panels)
        panel_text = f" │ Panel {self.active_panel_idx + 1}/{panel_count}" if panel_count > 1 else ""

        # Working directory (shortened)
        cwd = panel.working_dir if panel else Path.cwd()
        try:
            cwd_display = f"~/{cwd.relative_to(Path.home())}"
        except ValueError:
            cwd_display = str(cwd)
        cwd_text = f" │ [dim]{escape(cwd_display)}[/]"

        status = f"{session_text} │ {model_short}{code_text}{generating_text}{memory_text}{img_text}{mcp_text}{ctx_text}{panel_text}{cwd_text}"
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
            if self.active_panel._generating:
                self._show_info("[#e0af68]Wait for response to complete before switching sessions[/]")
                return
            self.active_panel.load_session(session_id)
            self._update_status()

    def _show_info(self, text: str) -> None:
        """Show info in the active panel."""
        if self.active_panel:
            self.active_panel.show_info(text)

    def _open_github_issue(self, template: str) -> None:
        """Open GitHub issue page with template."""
        url = f"https://github.com/dedalus-labs/wingman/issues/new?template={template}"
        webbrowser.open(url)
        self.notify(f"Opening {template.replace('.yml', '').replace('_', ' ')}...", timeout=2.0)

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

    def on_click(self, event) -> None:
        """Focus input when clicking anywhere in the main area."""
        panel = self.active_panel
        if panel:
            # Focus the input unless clicking on an interactive element
            from textual.widgets import Button, Input, ListView

            if not isinstance(event.widget, (Button, Input, ListView, ImageChip, ToolApproval)):
                # If there's a pending tool approval, focus that instead
                approvals = list(panel.query("ToolApproval"))
                if approvals:
                    approvals[0].focus()
                else:
                    panel.get_input().focus()

    def on_paste(self, event: events.Paste) -> None:
        """Route paste events to the active input if not already focused there."""
        panel = self.active_panel
        if not panel:
            return

        input_widget = panel.get_input()
        # If paste didn't go to the input (e.g., dropped while unfocused), route it there
        if self.focused != input_widget and event.text:
            # Focus the input and manually trigger paste handling
            input_widget.focus()
            input_widget._on_paste(event)
            event.stop()

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
        """Handle escape and arrow navigation for image chips."""
        # Handle escape only when no modal is open
        if event.key == "escape" and len(self.screen_stack) == 1:
            panel = self.active_panel
            if panel and panel._generating:
                panel._cancel_requested = True
                panel._generating = False  # Clear immediately
                self._update_status()
                # Remove thinking spinners
                for thinking in panel.query("Thinking"):
                    try:
                        thinking.remove()
                    except Exception:
                        pass
                # Remove pending tool approvals
                for approval in panel.query("ToolApproval"):
                    try:
                        approval.remove()
                    except Exception:
                        pass
                self.notify("Generation cancelled", severity="warning", timeout=2)
                event.stop()
                event.prevent_default()
                return
            elif panel:
                try:
                    input_widget = panel.query_one(f"#{panel.panel_id}-prompt", Input)
                    input_widget.value = ""
                    if hasattr(input_widget, "_pasted_content"):
                        input_widget._pasted_content = None
                        input_widget._paste_placeholder = None
                except Exception:
                    pass
                event.stop()
                event.prevent_default()
                return

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
        # Check for image extensions in various formats (plain, URL-encoded, backslash-escaped)
        text_lower = text.strip().strip("'\"").lower() if text else ""
        has_image_ext = any(
            text_lower.endswith(ext) or text_lower.endswith(ext.replace(".", "%2e"))
            for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
        )
        if text and has_image_ext:
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
            # Don't overwrite hint if actively cycling through completions for this exact input
            cycle = getattr(event.input, "_completion_cycle", None)
            if cycle and cycle.is_active_for(text, event.input.cursor_position):
                return
            matches = get_hint_candidates(text, event.input.cursor_position)
            formatted = "  ".join(f"[#7aa2f7]{cmd}[/]" for cmd in matches)
            hint.update(formatted if formatted else "")
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

        # Block input while generating
        if panel._generating:
            self.notify("Wait for response to complete", severity="warning", timeout=2)
            return

        # Activate this panel if it's not active
        if panel != self.active_panel:
            self._set_active_panel(self.panels.index(panel))

        text = (
            event.input.get_submit_value().strip() if hasattr(event.input, "get_submit_value") else event.value.strip()
        )

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
            panel.session_id = f"chat-{int(time.time() * 1000)}"
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
        
        # Save session immediately after user message
        save_session(panel.session_id, panel.messages)

        chat = panel.get_chat_container()
        thinking = Thinking(id="thinking")
        chat.mount(thinking)
        panel.get_scroll_container().scroll_end(animate=False)

        self._send_message(panel, text, thinking, images_to_send)

    @work(thread=False)
    async def _send_message(
        self, panel: ChatPanel, text: str, thinking: Thinking, images: list[CachedImage] | None = None
    ) -> None:
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
                    # Include both text and tool outputs so model has full context
                    content_parts = []
                    for seg in msg["segments"]:
                        if seg.get("type") == "text":
                            content_parts.append(seg["content"])
                        elif seg.get("type") == "tool":
                            # Include tool results so model knows what it did
                            cmd = seg.get("command", "")
                            output = seg.get("output", "")
                            content_parts.append(f"\n[Tool: {cmd}]\n{output}\n")
                    messages.append({"role": msg["role"], "content": "".join(content_parts)})
                else:
                    messages.append(msg.copy())

            # Replace the last user message with image version if images were attached
            if images and messages and messages[-1].get("role") == "user":
                messages[-1] = create_image_message_from_cache(text, images)

            if self.coding_mode:
                system_content = CODING_SYSTEM_PROMPT.format(cwd=panel.working_dir)
                # Include custom instructions (global first, then local)
                instructions = load_instructions(panel.working_dir)
                if instructions:
                    system_content += f"\n\n{instructions}"
                # Include project memory if available
                memory = load_memory()
                if memory.entries:
                    memory_text = "\n".join(e.content for e in memory.entries)
                    system_content += f"\n\n## Project Memory\n{memory_text}"
                system_msg = {"role": "system", "content": system_content}
                messages = [system_msg] + messages

            kwargs = {
                "messages": messages,
                "model": self.model,
                "stream": True,
            }
            if panel.mcp_servers:
                kwargs["mcp_servers"] = panel.mcp_servers
            if self.coding_mode:
                kwargs["tools"] = create_tools(panel.working_dir, panel.panel_id, panel.session_id)


            # Set session context for checkpoint tracking
            set_current_session(panel.session_id)
            clear_segments(panel.panel_id)  # Clear segment tracking for new response
            chat = panel.get_chat_container()

            streaming_widget = None
            widget_id = int(time.time() * 1000)  # Unique base ID per message

            panel._generating = True
            panel._cancel_requested = False
            was_cancelled = False
            self._update_status()
            try:
                stream = self.runner.run(**kwargs)

                # Handle both stream manager (event API) and raw iterator
                # Stream manager has __aenter__ but not __aiter__
                if hasattr(stream, "__aenter__") and not hasattr(stream, "__aiter__"):
                    # Event API stream (e.g., Gemini)
                    async with stream as event_stream:
                        async for event in event_stream:
                            if panel._cancel_requested:
                                was_cancelled = True
                                break
                            # Handle content.delta events
                            if hasattr(event, "type") and event.type == "content.delta":
                                content = getattr(event, "delta", None)
                                if content:
                                    if streaming_widget is None:
                                        widget_id += 1
                                        streaming_widget = StreamingText(id=f"streaming-{widget_id}")
                                        try:
                                            chat.mount(streaming_widget, before=thinking)
                                        except Exception:
                                            # Thinking widget was removed (cancelled)
                                            was_cancelled = True
                                            break
                                    add_text_segment(content, panel.panel_id)
                                    streaming_widget.append_text(content)
                                    panel.get_scroll_container().scroll_end(animate=False)
                                    await asyncio.sleep(0)
                else:
                    # Raw chunk iterator (OpenAI-style)
                    async for chunk in stream:
                        if panel._cancel_requested:
                            was_cancelled = True
                            break
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
                                    try:
                                        chat.mount(streaming_widget, before=thinking)
                                    except Exception:
                                        # Thinking widget was removed (cancelled)
                                        was_cancelled = True
                                        break
                                add_text_segment(delta.content, panel.panel_id)
                                streaming_widget.append_text(delta.content)
                                panel.get_scroll_container().scroll_end(animate=False)
                                await asyncio.sleep(0)
            finally:
                panel._generating = False
                set_current_session(None)

            if streaming_widget is not None:
                streaming_widget.mark_complete()
            self._update_status()

            try:
                thinking.remove()
            except Exception:
                pass

            segments = get_segments(panel.panel_id)
            if segments:
                panel.messages.append({"role": "assistant", "segments": segments})
                save_session(panel.session_id, panel.messages)
            elif not was_cancelled:
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
            # Save any partial segments before showing error
            segments = get_segments(panel.panel_id)
            if segments:
                panel.messages.append({"role": "assistant", "segments": segments})
                save_session(panel.session_id, panel.messages)
            else:
                # Only remove user message if there was no assistant response at all
                if panel.messages and panel.messages[-1].get("role") == "user":
                    panel.messages.pop()
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
            # Save any partial segments before handling error
            segments = get_segments(panel.panel_id)
            if segments:
                panel.messages.append({"role": "assistant", "segments": segments})
                save_session(panel.session_id, panel.messages)
            else:
                # Only remove user message if there was no assistant response at all
                if panel.messages and panel.messages[-1].get("role") == "user":
                    panel.messages.pop()
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                self._show_info("[#f7768e]Request timed out[/]")
            elif "cancelled" not in error_msg.lower():
                # Don't show error for cancellations, and don't use Rich markup
                panel.add_message("assistant", f"Error: {error_msg}")

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

    async def request_tool_approval(self, tool_name: str, command: str, panel_id: str | None = None) -> tuple[str, str]:
        """Request approval for a tool. Returns (result, feedback) where result is 'yes', 'always', or 'no'."""
        panel = None
        if panel_id:
            for p in self.panels:
                if p.panel_id == panel_id:
                    panel = p
                    break
        if not panel:
            panel = self.active_panel
        if not panel:
            return ("yes", "")
        chat = panel.get_chat_container()
        widget = ToolApproval(tool_name, command, id=f"tool-approval-{panel_id or 'default'}")
        # Mount before thinking spinner and hide spinner while awaiting approval
        thinking = None
        try:
            thinking = chat.query_one(Thinking)
            thinking.display = False
            chat.mount(widget, before=thinking)
        except Exception:
            chat.mount(widget)
        panel.get_scroll_container().scroll_end(animate=False)
        widget.focus()
        # Wait for widget to mount first
        while not widget.is_mounted:
            await asyncio.sleep(0.01)
        # Now wait for result or cancellation
        while widget.result is None:
            if not widget.is_mounted or panel._cancel_requested:
                return ("cancelled", "")
            await asyncio.sleep(0.05)
        result = widget.result
        try:
            widget.remove()
        except Exception:
            pass  # Already removed
        # Restore thinking spinner
        if thinking:
            thinking.display = True
        return result

    def action_quit(self) -> None:
        """Quit the app, or clear input if text present (double-tap to force exit)."""
        panel = self.active_panel
        if panel:
            try:
                input_widget = panel.query_one(f"#{panel.panel_id}-prompt", Input)
                if input_widget.value:
                    # Clear input instead of exiting
                    input_widget.value = ""
                    if hasattr(input_widget, "_pasted_content"):
                        input_widget._pasted_content = None
                    self.last_ctrl_c = None
                    return
            except Exception:
                pass

        # Double-tap detection (within 1 second)
        now = time.time()
        if self.last_ctrl_c and (now - self.last_ctrl_c) < 1.0:
            self.exit()
        else:
            self.last_ctrl_c = now
            if len(self.panels) > 1:
                self.notify("/close to close panel, Ctrl+C to quit", severity="warning", timeout=2.0)
            else:
                self.notify("Press Ctrl+C again to quit", severity="warning", timeout=1.5)

    def action_stop_generation(self) -> None:
        """Stop generation if active, otherwise clear input."""
        panel = self.active_panel
        if panel and panel._generating:
            panel._cancel_requested = True
            panel._generating = False  # Clear immediately
            self._update_status()
            # Remove thinking spinners
            for thinking in panel.query("Thinking"):
                try:
                    thinking.remove()
                except Exception:
                    pass
            # Remove pending tool approvals
            for approval in panel.query("ToolApproval"):
                try:
                    approval.remove()
                except Exception:
                    pass
            self.notify("Generation cancelled", severity="warning", timeout=2)
        elif panel:
            # Clear the input if not generating
            try:
                input_widget = panel.query_one(f"#{panel.panel_id}-prompt", Input)
                input_widget.value = ""
                if hasattr(input_widget, "_pasted_content"):
                    input_widget._pasted_content = None
                    input_widget._paste_placeholder = None
            except Exception:
                pass

    def action_background(self) -> None:
        """Request backgrounding of current command (Ctrl+B)."""
        panel = self.active_panel
        if panel:
            request_background(panel.panel_id)

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
        new_panel = self.panels[idx]
        new_panel.set_active(True)
        self._update_status()

    def action_split_panel(self) -> None:
        """Create a new panel (/split)."""
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

        def do_refresh():
            force_compact = len(self.panels) > 1
            for p in self.panels:
                try:
                    p.query_one(".panel-welcome")
                    p._show_welcome(force_compact=force_compact)
                except Exception:
                    pass

        # Extra frame delay to ensure layout is fully recalculated
        self.call_after_refresh(do_refresh)

    def on_resize(self, event) -> None:
        """Handle terminal resize - refresh welcome art."""
        self.call_after_refresh(self._refresh_welcome_art)

    def on_chat_panel_clicked(self, event: ChatPanel.Clicked) -> None:
        """Switch focus to clicked panel."""
        try:
            idx = self.panels.index(event.panel)
            if idx != self.active_panel_idx:
                self.panels[self.active_panel_idx].set_active(False)
                self.active_panel_idx = idx
                event.panel.set_active(True)
                self._update_status()
        except ValueError:
            pass

    def action_close_panel(self) -> None:
        """Close the active panel (/close)."""
        if len(self.panels) <= 1:
            self._show_info("Cannot close the last panel. Use Ctrl+C to quit.")
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
        """Switch to previous panel."""
        if len(self.panels) <= 1:
            return
        new_idx = (self.active_panel_idx - 1) % len(self.panels)
        self._set_active_panel(new_idx)

    def action_next_panel(self) -> None:
        """Switch to next panel."""
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

    def _mount_command_status(self, command: str, widget_id: str, panel_id: str | None = None) -> None:
        """Mount command status widget in the specified panel, before Thinking spinner."""
        # Find panel by ID, fall back to active panel
        panel = None
        if panel_id:
            for p in self.panels:
                if p.panel_id == panel_id:
                    panel = p
                    break
        if not panel:
            panel = self.active_panel
        if not panel:
            return

        chat = panel.get_chat_container()
        widget = CommandStatus(command, id=widget_id)
        # Mount before thinking spinner (search within this panel's chat only)
        try:
            thinking = chat.query_one(Thinking)
            chat.mount(widget, before=thinking)
        except Exception:
            chat.mount(widget)
        panel.get_scroll_container().scroll_end(animate=False)

    def _update_command_status(
        self, widget_id: str, status: str, output: str | None = None, panel_id: str | None = None
    ) -> None:
        """Update command status widget with final status and optional output."""
        try:
            widget = self.query_one(f"#{widget_id}", CommandStatus)
            widget.set_status(status, output)
        except Exception:
            pass

    def _update_thinking_status(self, status: str | None, panel_id: str | None = None) -> None:
        """Update the Thinking spinner with current tool status."""
        panel = None
        if panel_id:
            for p in self.panels:
                if p.panel_id == panel_id:
                    panel = p
                    break
        if not panel:
            panel = self.active_panel
        if not panel:
            return
        try:
            thinking = panel.get_chat_container().query_one(Thinking)
            thinking.set_status(status)
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

    def _cmd_delete(self, arg: str) -> None:
        panel = self.active_panel
        if not panel:
            return
        session_id = arg.strip() if arg else panel.session_id
        # Fall back to highlighted session in sidebar (but not the root node)
        if not session_id:
            try:
                tree = self.query_one("#sessions", Tree)
                if tree.cursor_node and tree.cursor_node != tree.root:
                    if tree.cursor_node.data:
                        session_id = str(tree.cursor_node.data)
                    else:
                        session_id = str(tree.cursor_node.label)
            except Exception:
                pass
        if not session_id:
            self._show_info("No session to delete")
            return
        delete_session(session_id)
        self._refresh_sessions()
        if panel.session_id == session_id:
            panel.session_id = None
            panel.clear_chat()
            panel.working_dir = Path.cwd()
            panel._show_welcome()
        self._show_info(f"Deleted session: {session_id}")
        self._update_status()

    def _cmd_mcp(self, arg: str) -> None:
        panel = self.active_panel
        if not panel:
            return
        if not arg:
            self._show_mcp_modal()
        elif arg == "clear":
            panel.mcp_servers = []
            self._show_info("Cleared all MCP servers")
            self._update_status()
        else:
            # Direct add: /mcp <server-url>
            if arg in panel.mcp_servers:
                self._show_info(f"MCP server already added: {arg}")
            else:
                panel.mcp_servers.append(arg)
                self._show_info(f"Added MCP server: {arg}")
                self._update_status()

    def _show_mcp_modal(self) -> None:
        from .ui.modals import MCPModal

        panel = self.active_panel
        if not panel:
            return
        self.push_screen(MCPModal(panel.mcp_servers.copy()), self._on_mcp_action)

    def _on_mcp_action(self, result: tuple[str, str | None] | None) -> None:
        if not result:
            return
        panel = self.active_panel
        if not panel:
            return
        action, server = result
        if action == "delete" and server:
            if server in panel.mcp_servers:
                panel.mcp_servers.remove(server)
                self.notify(f"Removed: {server}", timeout=2.0)
                self._update_status()
            # Reopen modal with updated list
            if panel.mcp_servers:
                self._show_mcp_modal()
        elif action == "add":
            self.action_add_mcp()

    def _cmd_code(self, arg: str) -> None:
        self.coding_mode = not self.coding_mode
        status = "[#9ece6a]ON[/]" if self.coding_mode else "[#f7768e]OFF[/]"
        self._show_info(f"Coding mode: {status}")
        self._update_status()

    def _cmd_cd(self, arg: str) -> None:
        panel = self.active_panel
        if not panel:
            return
        cwd = panel.working_dir
        if not arg:
            self._show_info(f"Working directory: {cwd}")
        else:
            new_dir = (cwd / Path(arg).expanduser()).resolve()
            if new_dir.is_dir():
                panel.working_dir = new_dir
                # Save to session if one exists
                if panel.session_id:
                    save_session_working_dir(panel.session_id, str(new_dir))
                self._show_info(f"Changed to: {new_dir}")
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
            self._show_info(
                f"[#9ece6a]Restored {len(restored)} file(s):[/]\n" + "\n".join(f"  • {f}" for f in restored)
            )
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
        from .memory import delete_entries
        from .ui.modals import MemoryModal

        if not arg or arg == "list":
            # Open memory browser modal
            memory = load_memory()
            self.push_screen(MemoryModal(memory.entries), self._on_memory_action)
        elif arg == "clear":
            clear_all()
            self._show_info("[#9ece6a]All memories cleared[/]")
        elif arg.startswith("add "):
            text = arg[4:].strip()
            if text:
                entry = add_entry(text)
                self._show_info(f"[#9ece6a]Added memory {entry.id}:[/] {text[:50]}{'...' if len(text) > 50 else ''}")
            else:
                self._show_info("Usage: /memory add <text>")
        elif arg.startswith("delete "):
            ids = arg[7:].split()
            if ids:
                n = delete_entries(ids)
                self._show_info(f"[#9ece6a]Deleted {n} memories[/]")
            else:
                self._show_info("Usage: /memory delete <id>")
        elif arg == "help":
            self._show_memory_help()
        else:
            self._show_memory_help()

    def _show_memory_help(self) -> None:
        help_text = """[bold #7aa2f7]Memory Commands[/]

[#7aa2f7]/memory[/]             Open memory browser
[#7aa2f7]/memory add[/] <text>  Add a note
[#7aa2f7]/memory clear[/]       Clear all memories

[bold #a9b1d6]In Browser[/]
  ↑↓   Navigate
  d    Delete highlighted
  a    Add new memory
  Esc  Close

[bold #a9b1d6]What is Memory?[/]
Project-specific notes injected into the AI context.
Useful for: API patterns, file locations, conventions.

[dim]Stored in ~/.wingman/memory/ per working directory.[/]"""
        self._show_info(help_text)

    def _on_memory_action(self, result: tuple[str, str | None] | None) -> None:
        if not result:
            return
        action, entry_id = result
        if action == "delete" and entry_id:
            from .memory import delete_entries

            n = delete_entries([entry_id])
            if n:
                self.notify(f"Deleted memory {entry_id}", timeout=2.0)
                # Reopen modal with updated list
                memory = load_memory()
                if memory.entries:
                    from .ui.modals import MemoryModal

                    self.push_screen(MemoryModal(memory.entries), self._on_memory_action)
        elif action == "add":
            from .ui.modals import InputModal

            self.push_screen(InputModal("Add Memory", "Enter note:"), self._on_memory_add)

    def _on_memory_add(self, text: str | None) -> None:
        if text and text.strip():
            entry = add_entry(text.strip())
            self.notify(f"Added memory {entry.id}", timeout=2.0)
            # Reopen modal
            memory = load_memory()
            from .ui.modals import MemoryModal

            self.push_screen(MemoryModal(memory.entries), self._on_memory_action)

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
        export_path = panel.working_dir / filename
        export_path.write_text(content)
        self._show_info(f"[#9ece6a]Exported to:[/] {export_path}")

    def _cmd_import(self, arg: str) -> None:
        if not arg:
            self._show_info("Usage: /import <path>")
            return
        panel = self.active_panel
        if not panel:
            return
        import_path = Path(arg).expanduser()
        if not import_path.is_absolute():
            import_path = panel.working_dir / import_path
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
            "exit": lambda: self.exit(),
            "ls": lambda: self._do_ls(arg or "*", self.active_panel.working_dir if self.active_panel else Path.cwd()),
            "ps": lambda: self._show_info(
                f"[bold #7aa2f7]Background Processes[/]\n{list_processes(self.active_panel.panel_id if self.active_panel else None)}"
            ),
            "processes": lambda: self._show_info(
                f"[bold #7aa2f7]Background Processes[/]\n{list_processes(self.active_panel.panel_id if self.active_panel else None)}"
            ),
            "kill": lambda: self._show_info(
                stop_process(arg, self.active_panel.panel_id if self.active_panel else None)
                if arg
                else "Usage: /kill <process_id>"
            ),
            "bug": lambda: self._open_github_issue("bug_report.yml"),
            "feature": lambda: self._open_github_issue("feature_request.yml"),
        }

        # Commands with complex logic
        complex_commands = {
            "rename": self._cmd_rename,
            "delete": self._cmd_delete,
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
    async def _do_ls(self, pattern: str, working_dir: Path) -> None:
        """List files asynchronously."""
        from .tools import _list_files_impl

        result = await _list_files_impl(pattern, ".", working_dir)
        self._show_info(f"[dim]{working_dir}[/]\n{result}")

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
        if panel._generating:
            self._show_info("[#e0af68]Wait for response to complete before starting new chat[/]")
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
        result = await self.push_screen_wait(SelectionModal("Open Session", sessions))
        if result:
            self._load_session(result)
            self._refresh_sessions()

    @work
    async def action_select_model(self) -> None:
        result = await self.push_screen_wait(SelectionModal("Select Model", MODELS))
        if result:
            self.model = result
            # Sync all panels' context model
            for panel in self.panels:
                panel.context.model = result
            self._show_info(f"Model: {result}")
            self._update_status()
            # Warn if new model has smaller context and needs compacting
            panel = self.active_panel
            if panel and panel.context.needs_compacting:
                self.notify("Context exceeds model limit. Run /compact", severity="warning")

    @work
    async def action_add_mcp(self) -> None:
        panel = self.active_panel
        if not panel:
            return
        options = []
        if MARKETPLACE_SERVERS:
            for server in MARKETPLACE_SERVERS:
                slug = server.get("slug", "")
                title = server.get("title") or slug.split("/")[-1]
                options.append(f"{title} ({slug})")
        options.append("+ Custom URL")

        result = await self.push_screen_wait(SelectionModal("Add MCP Server", options))
        if result:
            if result == "+ Custom URL":
                custom = await self.push_screen_wait(
                    InputModal("Add MCP Server", placeholder="Enter server URL or slug...")
                )
                if custom:
                    if custom in panel.mcp_servers:
                        self._show_info(f"MCP server already added: {custom}")
                    else:
                        panel.mcp_servers.append(custom)
                        self._show_info(f"Added MCP server: {custom}")
                        self._update_status()
            else:
                match = re.search(r"\(([^)]+)\)$", result)
                if match:
                    slug = match.group(1)
                    if slug in panel.mcp_servers:
                        self._show_info(f"MCP server already added: {slug}")
                    else:
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
            self._show_info(
                f"[#9ece6a]Restored {len(restored)} file(s) from {checkpoint.id}:[/]\n"
                + "\n".join(f"  • {f}" for f in restored)
            )
        else:
            self._show_info("[#f7768e]Failed to restore checkpoint[/]")

    def action_help(self) -> None:
        panel = self.active_panel
        bg_count = len(get_background_processes(panel.panel_id if panel else None))
        cp_count = len(get_checkpoint_manager()._checkpoints)
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
  [#7aa2f7]/diff[/] [dim]\\[id][/]  Show changes since checkpoint

[bold #a9b1d6]Memory[/]
  [#7aa2f7]/memory[/]         Open memory browser (TUI)
  [#7aa2f7]/memory add[/]     Add note
  [#7aa2f7]/memory help[/]    Show memory help

[bold #a9b1d6]Export/Import[/]
  [#7aa2f7]/export[/]         Export session to markdown
  [#7aa2f7]/export json[/]    Export as JSON
  [#7aa2f7]/import <path>[/]  Import from file

[bold #a9b1d6]Config[/]
  [#7aa2f7]/model[/]          Switch model
  [#7aa2f7]/context[/]        Show context usage

[bold #a9b1d6]App[/]
  [#7aa2f7]/exit[/]           Quit Wingman

[bold #a9b1d6]Feedback[/]
  [#7aa2f7]/bug[/]            Report a bug
  [#7aa2f7]/feature[/]        Request a feature

[bold #a9b1d6]Shortcuts[/]
  [#7aa2f7]F1[/] or [#7aa2f7]Ctrl+/[/]  This help
  [#7aa2f7]Ctrl+Z[/]          Undo (restore last checkpoint)
  [#7aa2f7]Ctrl+B[/]          Background running command

[dim]Working dir: {panel.working_dir if panel else Path.cwd()}[/]
[dim]Panels: {panel_count} · Background: {bg_count} · Checkpoints: {cp_count} · Images: {img_count}[/]"""
        self._show_info(help_text)


def main():
    import argparse
    import sys

    # Load environment variables from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(prog="wingman", description="Wingman - AI coding assistant for the terminal")
    parser.add_argument(
        "-p",
        "--print",
        dest="prompt",
        metavar="PROMPT",
        help="Run in headless mode with the given prompt (non-interactive)",
    )
    parser.add_argument("-m", "--model", help="Model to use (e.g., anthropic/claude-sonnet-4-20250514)")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output in headless mode")
    parser.add_argument(
        "--allowed-tools", help="Comma-separated list of allowed tools (e.g., read_file,write_file,run_command)"
    )
    parser.add_argument("-C", "--working-dir", help="Working directory for file operations")

    args = parser.parse_args()

    # Headless mode
    if args.prompt:
        import asyncio
        from pathlib import Path

        from .headless import run_headless

        working_dir = Path(args.working_dir) if args.working_dir else None
        allowed_tools = args.allowed_tools.split(",") if args.allowed_tools else None

        exit_code = asyncio.run(
            run_headless(
                prompt=args.prompt,
                model=args.model,
                working_dir=working_dir,
                allowed_tools=allowed_tools,
                verbose=args.verbose,
            )
        )
        sys.exit(exit_code)

    # Interactive TUI mode
    app = WingmanApp()
    app.run()


if __name__ == "__main__":
    main()
