"""Panel management mixin for wingman.

Split, close, navigate, and resize multi-panel layouts.
Methods are discovered by Textual's action dispatch via MRO.

"""

from __future__ import annotations

from textual.containers import Horizontal


class PanelMixin:
    """Panel orchestration methods mixed into WingmanApp.

    Textual dispatches ``action_*`` via ``getattr`` which traverses
    the MRO, so these methods work identically to methods defined
    directly on the App class.

    """

    def set_active_panel(self, idx: int) -> None:
        """Set the active panel by index."""
        if idx < 0 or idx >= len(self.panels):
            return
        if self.active_panel:
            self.active_panel.set_active(False)
        self.active_panel_idx = idx
        new_panel = self.panels[idx]
        new_panel.set_active(True)
        self.update_status()

    def create_panel(
        self,
        *,
        initial_session_id: str | None = None,
        initial_input: str | None = None,
    ):
        """Create and mount a new panel, returning it. Returns None if at panel cap."""
        if len(self.panels) >= 4:
            self.show_info("Maximum 4 panels allowed")
            return None
        from .ui import ChatPanel

        container = self.query_one("#panels-container", Horizontal)
        panel = ChatPanel(initial_session_id=initial_session_id, initial_input=initial_input)
        self.panels.append(panel)
        container.mount(panel)
        self.call_after_refresh(self._refresh_welcome_art)
        self.set_active_panel(len(self.panels) - 1)
        self.update_status()
        return panel

    def action_split_panel(self) -> None:
        """Create a new panel."""
        self.create_panel()

    def on_branch_marker_open_fork(self, event) -> None:
        """Open the forked session in a new panel, or focus it if already open."""
        fork_id = event.fork_session_id
        if not fork_id:
            return
        for idx, existing in enumerate(self.panels):
            if existing.session_id == fork_id:
                self.set_active_panel(idx)
                return
        panel = self.create_panel(initial_session_id=fork_id)
        if panel is not None:
            self.refresh_sessions()

    def _refresh_welcome_art(self) -> None:
        """Re-render welcome art on panels that have it."""

        def do_refresh():
            force_compact = len(self.panels) > 1
            for p in self.panels:
                try:
                    p.query_one(".panel-welcome")
                    p._show_welcome(force_compact=force_compact)
                except Exception:
                    pass

        self.call_after_refresh(do_refresh)

    def on_resize(self, event) -> None:
        """Handle terminal resize."""
        self.call_after_refresh(self._refresh_welcome_art)

    def on_chat_panel_clicked(self, event) -> None:
        """Switch focus to clicked panel."""
        try:
            idx = self.panels.index(event.panel)
            if idx != self.active_panel_idx:
                self.panels[self.active_panel_idx].set_active(False)
                self.active_panel_idx = idx
                event.panel.set_active(True)
                self.update_status()
        except ValueError:
            pass

    def action_close_panel(self) -> None:
        """Close the active panel."""
        if len(self.panels) <= 1:
            self.show_info("Cannot close the last panel. Use Ctrl+C to quit.")
            return
        panel = self.active_panel
        if not panel:
            return
        idx = self.active_panel_idx
        new_idx = idx - 1 if idx > 0 else 0
        self.active_panel_idx = new_idx
        panel.remove()
        self.panels.remove(panel)
        self.call_after_refresh(self._refresh_welcome_art)
        self.panels[new_idx].set_active(True)
        self.update_status()

    def action_prev_panel(self) -> None:
        """Switch to previous panel."""
        if len(self.panels) <= 1:
            return
        new_idx = (self.active_panel_idx - 1) % len(self.panels)
        self.set_active_panel(new_idx)

    def action_next_panel(self) -> None:
        """Switch to next panel."""
        if len(self.panels) <= 1:
            return
        new_idx = (self.active_panel_idx + 1) % len(self.panels)
        self.set_active_panel(new_idx)

    def action_goto_panel_1(self) -> None:
        if len(self.panels) >= 1:
            self.set_active_panel(0)

    def action_goto_panel_2(self) -> None:
        if len(self.panels) >= 2:
            self.set_active_panel(1)

    def action_goto_panel_3(self) -> None:
        if len(self.panels) >= 3:
            self.set_active_panel(2)

    def action_goto_panel_4(self) -> None:
        if len(self.panels) >= 4:
            self.set_active_panel(3)
