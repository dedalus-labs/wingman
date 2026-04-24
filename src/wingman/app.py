"""Main Wingman application."""

import asyncio
import contextlib
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

from .checkpoints import get_checkpoint_manager
from .commands import Commands
from .config import (
    APP_CREDIT,
    APP_NAME,
    APP_VERSION,
    MARKETPLACE_SERVERS,
    MODELS,
    fetch_marketplace_servers,
    load_api_key,
    load_base_url,
)
from .context import AUTO_COMPACT_THRESHOLD, CompactionController
from .events import EventHandler
from .fork import ForkController
from .memory import load_memory
from .panels import PanelMixin
from .sessions import load_sessions
from .streaming import StreamingController
from .tool_bridge import ToolBridgeMixin
from .tools import (
    check_completed_processes,
    get_background_processes,
    get_pending_edit,
    request_background,
    set_app_instance,
)
from .ui import (
    APIKeyScreen,
    ChatPanel,
    ImageChip,
    InputModal,
    MultilineInput,
    SelectionModal,
    Thinking,
    ToolApproval,
)


class WingmanApp(PanelMixin, ToolBridgeMixin, App):
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
        Binding("ctrl+d", "exit_if_empty", "Quit", priority=True, show=False),
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
        self.cmds = Commands(self)
        self.streaming = StreamingController(self)
        self.compaction = CompactionController(self)
        self.events = EventHandler(self)
        self.forking = ForkController(self)
        self.scroll_sensitivity_y = 0.6
        self.client: AsyncDedalus | None = None
        self.runner: DedalusRunner | None = None
        self.model = MODELS[0]
        self.coding_mode: bool = True
        self.panels: list[ChatPanel] = []
        self.active_panel_idx: int = 0
        self.last_ctrl_c: float | None = None

    def _init_client(self, api_key: str) -> None:
        """Initialize Dedalus client with API key."""
        base_url = load_base_url()
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncDedalus(**kwargs)
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
            with Vertical(id="main"), Horizontal(id="panels-container"):
                panel = ChatPanel()
                self.panels.append(panel)
                yield panel
        yield Static(id="status")

    def on_mount(self) -> None:
        self.refresh_sessions()
        self.update_status()
        self.query_one("#sidebar").display = False
        # Set first panel as active
        if self.panels:
            self.panels[0].set_active(True)
        # Check for API key
        api_key = load_api_key()
        if api_key:
            self._init_client(api_key)
        else:
            self.push_screen(APIKeyScreen(), self.on_api_key_entered)
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

    @work(thread=False)
    async def send_message(self, panel, text, thinking, images=None) -> None:
        """Schedule streaming a user message as a Textual worker.

        Sync event handlers (on_submit) fire-and-forget into this. The
        @work decorator turns the call into a scheduled worker so the
        coroutine isn't orphaned.
        """
        await self.streaming.send_message(panel, text, thinking, images)

    @work(thread=False)
    async def do_compact(self) -> None:
        """Schedule /compact as a worker (sync dispatch lambdas need @work)."""
        await self.compaction.compact()

    def _check_background_processes(self) -> None:
        """Periodic check for completed background processes."""
        completed = check_completed_processes()
        for _panel_id, bg_id, exit_code, command in completed:
            # Shorten command for display
            cmd_short = command[:40] + "..." if len(command) > 40 else command
            if exit_code == 0:
                self.notify(f"[{bg_id}] completed: {cmd_short}", timeout=5.0)
            else:
                self.notify(f"[{bg_id}] failed (exit {exit_code}): {cmd_short}", timeout=5.0, severity="error")

    def on_api_key_entered(self, api_key: str | None) -> None:
        """Callback when API key is entered."""
        if api_key:
            self._init_client(api_key)
            if self.active_panel:
                self.active_panel.get_input().focus()

    def update_status(self) -> None:
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
        remaining = 1.0 - panel.context.usage_percent if panel else 1.0
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

        base_url = load_base_url()
        base_text = f" │ [#e0af68]{base_url.split('//')[1][:30]}[/]" if base_url else ""
        status = f"{session_text} │ {model_short}{base_text}{code_text}{generating_text}{memory_text}{img_text}{mcp_text}{ctx_text}{panel_text}{cwd_text}"
        self.query_one("#status", Static).update(Text.from_markup(status))

    def refresh_sessions(self) -> None:
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
                self.show_info("[#e0af68]Wait for response to complete before switching sessions[/]")
                return
            self.active_panel.load_session(session_id)
            self.update_status()

    def show_info(self, text: str) -> None:
        """Show info in the active panel."""
        if self.active_panel:
            self.active_panel.show_info(text)

    def open_github_issue(self, template: str) -> None:
        """Open GitHub issue page with template."""
        url = f"https://github.com/dedalus-labs/wingman/issues/new?template={template}"
        webbrowser.open(url)
        self.notify(f"Opening {template.replace('.yml', '').replace('_', ' ')}...", timeout=2.0)

    def show_context_info(self) -> None:
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
        self.show_info(info)

    def on_descendant_focus(self, event) -> None:
        self.events.on_descendant_focus(event)

    def on_click(self, event) -> None:
        self.events.on_click(event)

    def on_paste(self, event: events.Paste) -> None:
        self.events.on_paste(event)

    @on(MultilineInput.ImageDropped)
    def on_image_dropped(self, event: MultilineInput.ImageDropped) -> None:
        self.events.on_image_dropped(event)

    @on(ImageChip.Removed)
    def on_image_chip_removed(self, event: ImageChip.Removed) -> None:
        self.events.on_image_chip_removed(event)

    @on(ImageChip.Navigate)
    def on_image_chip_navigate(self, event: ImageChip.Navigate) -> None:
        self.events.on_image_chip_navigate(event)

    def on_key(self, event) -> None:
        self.events.on_key(event)

    @on(Input.Changed, ".panel-prompt")
    def on_input_changed(self, event: Input.Changed) -> None:
        self.events.on_input_changed(event)

    @on(Input.Submitted, ".panel-prompt")
    def on_submit(self, event: Input.Submitted) -> None:
        self.events.on_submit(event)

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
        with contextlib.suppress(Exception):
            widget.remove()
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
            self.update_status()
            # Remove thinking spinners
            for thinking in panel.query("Thinking"):
                with contextlib.suppress(Exception):
                    thinking.remove()
            # Remove pending tool approvals
            for approval in panel.query("ToolApproval"):
                with contextlib.suppress(Exception):
                    approval.remove()
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

    # Panel management methods provided by PanelMixin
    # Tool bridge methods provided by ToolBridgeMixin

    def handle_command(self, cmd: str) -> None:
        """Delegate slash commands to self.cmds."""
        self.cmds.dispatch(cmd)

    # Command methods extracted to self.cmds (commands.py)

    @work(thread=False)
    async def do_ls(self, pattern: str, working_dir: Path) -> None:
        """List files asynchronously."""
        from .tools import _list_files_impl

        result = await _list_files_impl(pattern, ".", working_dir)
        self.show_info(f"[dim]{working_dir}[/]\n{result}")

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
            self.show_info("[#e0af68]Wait for response to complete before starting new chat[/]")
            return
        panel.session_id = None
        panel.context.clear()
        panel._show_welcome()
        self.update_status()
        panel.get_input().focus()

    @work
    async def action_open_session(self) -> None:
        sessions = list(load_sessions().keys())
        if not sessions:
            self.show_info("No saved sessions")
            return
        result = await self.push_screen_wait(SelectionModal("Open Session", sessions))
        if result:
            self._load_session(result)
            self.refresh_sessions()

    @work
    async def action_select_model(self) -> None:
        result = await self.push_screen_wait(SelectionModal("Select Model", MODELS))
        if result:
            self.model = result
            # Sync all panels' context model
            for panel in self.panels:
                panel.context.model = result
            self.show_info(f"Model: {result}")
            self.update_status()
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
                        self.show_info(f"MCP server already added: {custom}")
                    else:
                        panel.mcp_servers.append(custom)
                        self.show_info(f"Added MCP server: {custom}")
                        self.update_status()
            else:
                match = re.search(r"\(([^)]+)\)$", result)
                if match:
                    slug = match.group(1)
                    if slug in panel.mcp_servers:
                        self.show_info(f"MCP server already added: {slug}")
                    else:
                        panel.mcp_servers.append(slug)
                        self.show_info(f"Added MCP server: {slug}")
                        self.update_status()

    def action_clear_chat(self) -> None:
        """Clear chat in the active panel."""
        panel = self.active_panel
        if not panel:
            return
        panel.clear_chat()
        self.update_status()

    def action_undo(self) -> None:
        """Undo last file change by restoring most recent checkpoint for this session."""
        cp_manager = get_checkpoint_manager()
        panel = self.active_panel
        session_id = panel.session_id if panel else None
        recent = cp_manager.list_recent(1, session_id=session_id)
        if not recent:
            self.show_info("[#e0af68]No checkpoints available to undo in this session[/]")
            return
        checkpoint = recent[0]
        restored = cp_manager.restore(checkpoint.id)
        if restored:
            self.show_info(
                f"[#9ece6a]Restored {len(restored)} file(s) from {checkpoint.id}:[/]\n"
                + "\n".join(f"  • {f}" for f in restored)
            )
        else:
            self.show_info("[#f7768e]Failed to restore checkpoint[/]")

    def action_exit_if_empty(self) -> None:
        """Exit the app on Ctrl+D when the active input has no text."""
        focused = self.screen.focused
        if isinstance(focused, Input) and not (focused.value or "").strip():
            self.exit()

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

[bold #a9b1d6]Forking[/]
  [#7aa2f7]/fork[/]           Open the fork picker (pick a point in history)
  [#7aa2f7]/fork <n>[/]       Rewind n user turns, then fork (0 = clone all)
  [#7aa2f7]/forks[/]          List forks of this session

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
        self.show_info(help_text)
