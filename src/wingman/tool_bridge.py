"""Tool-to-UI bridge mixin for wingman.

Thread-safe methods that the tool execution layer (tools.py) calls
to mount widgets, update command status, and show diff modals.

"""

from __future__ import annotations


class ToolBridgeMixin:
    """Bridge between tool execution and TUI widgets.

    These methods are called from tools.py via the app instance
    reference. They handle thread-safe widget mounting and updates.

    """

    def _mount_command_status(self, command: str, widget_id: str, panel_id: str | None = None) -> None:
        """Mount a command status widget in the chat."""
        from .ui import CommandStatus

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
        thinking_widgets = list(chat.query("Thinking"))
        if thinking_widgets:
            chat.mount(widget, before=thinking_widgets[0])
        else:
            chat.mount(widget)
        panel.get_scroll_container().scroll_end(animate=False)

    def _update_command_status(
        self, widget_id: str, status: str, output: str | None = None, panel_id: str | None = None
    ) -> None:
        """Update a command status widget."""
        from .ui import CommandStatus

        try:
            widget = self.query_one(f"#{widget_id}", CommandStatus)
            widget.set_status(status, output)
        except Exception:
            pass

    def _update_thinking_status(self, status: str | None, panel_id: str | None = None) -> None:
        """Update the thinking spinner status text."""
        from .ui import Thinking

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
            thinking = panel.query_one("Thinking", Thinking)
            thinking.set_status(status)
        except Exception:
            pass

    async def _show_diff_modal(self, path: str, old_string: str, new_string: str) -> None:
        """Display diff modal and handle approval."""
        from .tools import set_edit_result
        from .ui import DiffModal

        result = await self.push_screen_wait(DiffModal(path, old_string, new_string))
        set_edit_result(result)
