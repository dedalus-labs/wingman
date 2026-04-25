"""Slash command handlers for wingman.

Each public method on ``Commands`` handles one ``/slash`` command.
The ``dispatch`` method routes input to the correct handler.

"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from .checkpoints import get_checkpoint_manager
from .config import load_base_url
from .export import export_session_json, export_session_markdown
from .memory import add_entry, clear_all, load_memory
from .sessions import delete_session, rename_session, save_session_working_dir
from .tools import list_processes, stop_process

if TYPE_CHECKING:
    from .app import WingmanApp


class Commands:
    """PyTorch-style command module attached to the app as ``self.cmds``.

    All methods are public. The app delegates ``/slash`` input here via
    ``self.cmds.dispatch(cmd_string)``.

    """

    def __init__(self, app: WingmanApp) -> None:
        self.app = app

    def dispatch(self, cmd: str) -> None:
        """Parse and route a ``/command arg`` string.

        Args:
            cmd: Raw input starting with ``/``.

        """
        parts = cmd[1:].split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        handlers = {
            "new": lambda: self.app.action_new_session(),
            "split": lambda: self.app.action_split_panel(),
            "close": lambda: self.app.action_close_panel(),
            "model": lambda: self.app.action_select_model(),
            "compact": lambda: self.app.do_compact(),
            "context": lambda: self.app.show_context_info(),
            "key": lambda: self.app.push_screen(self._api_key_screen(), self.app.on_api_key_entered),
            "base_url": lambda: self.app.push_screen(self._base_url_screen(), self.app.on_base_url_entered),
            "clear": lambda: self.app.action_clear_chat(),
            "help": lambda: self.app.action_help(),
            "quit": lambda: self.app.exit(),
            "exit": lambda: self.app.exit(),
            "ls": lambda: self.ls(arg),
            "ps": lambda: self.ps(),
            "processes": lambda: self.ps(),
            "kill": lambda: self.kill(arg),
            "bug": lambda: self.bug(),
            "feature": lambda: self.feature(),
            "rename": lambda: self.rename(arg),
            "delete": lambda: self.delete(arg),
            "mcp": lambda: self.mcp(arg),
            "code": lambda: self.code(arg),
            "cd": lambda: self.cd(arg),
            "history": lambda: self.history(arg),
            "rollback": lambda: self.rollback(arg),
            "diff": lambda: self.diff(arg),
            "memory": lambda: self.memory(arg),
            "export": lambda: self.export(arg),
            "import": lambda: self.import_file(arg),
            "fork": lambda: self.app.forking.fork(arg),
            "forks": lambda: self.app.forking.forks(arg),
        }

        handler = handlers.get(command)
        if handler:
            handler()
        else:
            self.app.show_info(f"Unknown command: {command}")

    # --- Simple commands ---

    def ps(self) -> None:
        """List background processes."""
        panel = self.app.active_panel
        pid = panel.panel_id if panel else None
        self.app.show_info(f"[bold #7aa2f7]Background Processes[/]\n{list_processes(pid)}")

    def kill(self, arg: str) -> None:
        """Stop a background process by ID."""
        if not arg:
            self.app.show_info("Usage: /kill <process_id>")
            return
        panel = self.app.active_panel
        pid = panel.panel_id if panel else None
        self.app.show_info(stop_process(arg, pid))

    def bug(self) -> None:
        """Open pre-filled bug report."""
        self.app.open_github_issue("bug_report.yml")

    def feature(self) -> None:
        """Open feature request."""
        self.app.open_github_issue("feature_request.yml")

    def ls(self, arg: str) -> None:
        """List files in working directory."""
        panel = self.app.active_panel
        if not panel:
            return
        self.app.do_ls(arg or "*", panel.working_dir)

    # --- Session commands ---

    def rename(self, arg: str) -> None:
        """Rename the active session."""
        panel = self.app.active_panel
        if not panel or not panel.session_id:
            self.app.show_info("No active session to rename")
        elif arg:
            if rename_session(panel.session_id, arg):
                old_name = panel.session_id
                panel.session_id = arg
                self.app.refresh_sessions()
                self.app.update_status()
                self.app.show_info(f"Renamed '{old_name}' → '{arg}'")
            else:
                self.app.show_info(f"Could not rename: '{arg}' may already exist")
        else:
            self.app.show_info("Usage: /rename <new-name>")

    def delete(self, arg: str) -> None:
        """Delete a session."""
        panel = self.app.active_panel
        if not panel:
            return
        session_id = arg.strip() if arg else panel.session_id
        if not session_id:
            from textual.widgets import Tree

            try:
                tree = self.app.query_one("#sessions", Tree)
                if tree.cursor_node and tree.cursor_node != tree.root:
                    session_id = str(tree.cursor_node.data) if tree.cursor_node.data else str(tree.cursor_node.label)
            except Exception:
                pass
        if not session_id:
            self.app.show_info("No session to delete")
            return
        delete_session(session_id)
        self.app.refresh_sessions()
        if panel.session_id == session_id:
            panel.session_id = None
            panel.clear_chat()
            panel.working_dir = Path.cwd()
            panel._show_welcome()
        self.app.show_info(f"Deleted session: {session_id}")
        self.app.update_status()

    # --- Navigation commands ---

    def cd(self, arg: str) -> None:
        """Change working directory."""
        panel = self.app.active_panel
        if not panel:
            return
        cwd = panel.working_dir
        if not arg:
            self.app.show_info(f"Working directory: {cwd}")
        else:
            new_dir = (cwd / Path(arg).expanduser()).resolve()
            if new_dir.is_dir():
                panel.working_dir = new_dir
                if panel.session_id:
                    save_session_working_dir(panel.session_id, str(new_dir))
                self.app.show_info(f"Changed to: {new_dir}")
                self.app.update_status()
            else:
                self.app.show_info(f"Not a directory: {arg}")

    def code(self, arg: str) -> None:
        """Toggle coding mode."""
        self.app.coding_mode = not self.app.coding_mode
        status = "[#9ece6a]ON[/]" if self.app.coding_mode else "[#f7768e]OFF[/]"
        self.app.show_info(f"Coding mode: {status}")
        self.app.update_status()

    # --- MCP commands ---

    def mcp(self, arg: str) -> None:
        """Manage MCP servers."""
        panel = self.app.active_panel
        if not panel:
            return
        if not arg:
            self.show_mcp_modal()
        elif arg == "clear":
            panel.mcp_servers = []
            self.app.show_info("Cleared all MCP servers")
            self.app.update_status()
        else:
            if arg in panel.mcp_servers:
                self.app.show_info(f"MCP server already added: {arg}")
            else:
                panel.mcp_servers.append(arg)
                self.app.show_info(f"Added MCP server: {arg}")
                self.app.update_status()

    def show_mcp_modal(self) -> None:
        """Open the MCP server browser modal."""
        from .ui.modals import MCPModal

        panel = self.app.active_panel
        if not panel:
            return
        self.app.push_screen(MCPModal(panel.mcp_servers.copy()), self.on_mcp_action)

    def on_mcp_action(self, result: tuple[str, str | None] | None) -> None:
        """Handle MCP modal result."""
        if not result:
            return
        panel = self.app.active_panel
        if not panel:
            return
        action, server = result
        if action == "delete" and server:
            if server in panel.mcp_servers:
                panel.mcp_servers.remove(server)
                self.app.notify(f"Removed: {server}", timeout=2.0)
                self.app.update_status()
            if panel.mcp_servers:
                self.show_mcp_modal()
        elif action == "add":
            self.app.action_add_mcp()

    # --- Checkpoint commands ---

    def history(self, arg: str) -> None:
        """Show recent checkpoints."""
        panel = self.app.active_panel
        cp_manager = get_checkpoint_manager()
        session_id = panel.session_id if panel else None
        checkpoints = cp_manager.list_recent(15, session_id=session_id)
        if not checkpoints:
            self.app.show_info(
                "No checkpoints for this session. Checkpoints are created automatically before file edits."
            )
        else:
            lines = ["[bold #7aa2f7]Checkpoints[/] (use /rollback <id> to restore)\n"]
            for cp in checkpoints:
                ts = time.strftime("%H:%M:%S", time.localtime(cp.timestamp))
                files = ", ".join(Path(f).name for f in cp.files)
                lines.append(f"  [#9ece6a]{cp.id}[/] [{ts}] {cp.description}")
                lines.append(f"    [dim]{files}[/]")
            self.app.show_info("\n".join(lines))

    def rollback(self, arg: str) -> None:
        """Restore a checkpoint."""
        if not arg:
            self.app.show_info("Usage: /rollback <checkpoint_id>\nUse /history to see available checkpoints.")
            return
        panel = self.app.active_panel
        cp_manager = get_checkpoint_manager()
        cp = cp_manager.get(arg)
        session_id = panel.session_id if panel else None
        if cp and cp.session_id and cp.session_id != session_id:
            self.app.show_info(f"[#e0af68]Checkpoint {arg} belongs to a different session.[/]")
            return
        restored = cp_manager.restore(arg)
        if restored:
            self.app.show_info(
                f"[#9ece6a]Restored {len(restored)} file(s):[/]\n" + "\n".join(f"  • {f}" for f in restored)
            )
        else:
            self.app.show_info(f"[#f7768e]Checkpoint not found: {arg}[/]")

    def diff(self, arg: str) -> None:
        """Show changes since a checkpoint."""
        panel = self.app.active_panel
        cp_manager = get_checkpoint_manager()
        session_id = panel.session_id if panel else None
        if not arg:
            recent = cp_manager.list_recent(1, session_id=session_id)
            if recent:
                arg = recent[0].id
            else:
                self.app.show_info("No checkpoints available for this session. Use /diff <checkpoint_id>")
                return
        diffs = cp_manager.diff(arg)
        if not diffs:
            self.app.show_info(f"No changes since checkpoint {arg}")
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
            self.app.show_info("\n".join(lines))

    # --- Memory commands ---

    def memory(self, arg: str) -> None:
        """Manage project memory."""
        from .memory import delete_entries
        from .ui.modals import MemoryModal

        if not arg or arg == "list":
            memory = load_memory()
            self.app.push_screen(MemoryModal(memory.entries), self.on_memory_action)
        elif arg == "clear":
            clear_all()
            self.app.show_info("[#9ece6a]All memories cleared[/]")
        elif arg.startswith("add "):
            text = arg[4:].strip()
            if text:
                entry = add_entry(text)
                preview = text[:50] + ("..." if len(text) > 50 else "")
                self.app.show_info(f"[#9ece6a]Added memory {entry.id}:[/] {preview}")
            else:
                self.app.show_info("Usage: /memory add <text>")
        elif arg.startswith("delete "):
            ids = arg[7:].split()
            if ids:
                n = delete_entries(ids)
                self.app.show_info(f"[#9ece6a]Deleted {n} memories[/]")
            else:
                self.app.show_info("Usage: /memory delete <id>")
        else:
            self.show_memory_help()

    def show_memory_help(self) -> None:
        """Display memory command usage."""
        self.app.show_info("""[bold #7aa2f7]Memory Commands[/]

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

[dim]Stored in ~/.wingman/memory/ per working directory.[/]""")

    def on_memory_action(self, result: tuple[str, str | None] | None) -> None:
        """Handle memory modal result."""
        if not result:
            return
        action, entry_id = result
        if action == "delete" and entry_id:
            from .memory import delete_entries
            from .ui.modals import MemoryModal

            n = delete_entries([entry_id])
            if n:
                self.app.notify(f"Deleted memory {entry_id}", timeout=2.0)
                memory = load_memory()
                if memory.entries:
                    self.app.push_screen(MemoryModal(memory.entries), self.on_memory_action)
        elif action == "add":
            from .ui.modals import InputModal

            self.app.push_screen(InputModal("Add Memory", "Enter note:"), self.on_memory_add)

    def on_memory_add(self, text: str | None) -> None:
        """Handle memory add modal result."""
        if text and text.strip():
            from .ui.modals import MemoryModal

            entry = add_entry(text.strip())
            self.app.notify(f"Added memory {entry.id}", timeout=2.0)
            memory = load_memory()
            self.app.push_screen(MemoryModal(memory.entries), self.on_memory_action)

    # --- Export/Import ---

    def export(self, arg: str) -> None:
        """Export session to file."""
        panel = self.app.active_panel
        if not panel or not panel.messages:
            self.app.show_info("No messages to export")
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
        self.app.show_info(f"[#9ece6a]Exported to:[/] {export_path}")

    def import_file(self, arg: str) -> None:
        """Import messages from file."""
        if not arg:
            self.app.show_info("Usage: /import <path>")
            return
        panel = self.app.active_panel
        if not panel:
            return
        from .export import import_session_from_file

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
            self.app.update_status()
            self.app.show_info(f"[#9ece6a]Imported {count} messages as context[/]")
        else:
            self.app.show_info(f"[#f7768e]Could not import from:[/] {arg}")

    # --- Private helpers ---

    def _api_key_screen(self):
        from .ui.modals import APIKeyScreen

        return APIKeyScreen()

    def _base_url_screen(self):
        from .ui.modals import BaseUrlScreen

        return BaseUrlScreen(current=load_base_url() or "")
