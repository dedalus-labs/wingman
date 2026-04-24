"""Conversation forking: controller + /fork, /forks handlers.

Forking copies a slice of the active session's messages into a new
session with parent-lineage metadata. The UI picks a cut point via
``ForkPickerModal`` (or ``/fork <n>`` rewinds N user turns).

"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .sessions import fork_session_copy, list_forks, save_session

if TYPE_CHECKING:
    from .app import WingmanApp


class ForkController:
    """App-level fork orchestration.

    Runs the /fork and /forks commands, opens the picker modal, creates
    forked sessions, and inline-re-renders the parent panel so a fresh
    ``BranchMarker`` appears without a manual reload. Attached as
    ``self.forking``.

    """

    def __init__(self, app: WingmanApp) -> None:
        self.app = app

    def fork(self, arg: str) -> None:
        """Run /fork.

        No arg opens the picker modal. Integer arg rewinds that many
        user turns and forks directly (bypasses the picker).

        """
        panel = self.app.active_panel
        if not panel or not panel.messages:
            self.app.show_info("No messages to fork")
            return
        if panel._generating:
            self.app.show_info("[#e0af68]Wait for response to complete before forking[/]")
            return

        if not arg.strip():
            from .ui.modals import ForkPickerModal

            self.app.push_screen(ForkPickerModal(list(panel.messages)), self.on_fork_picked)
            return

        try:
            n = int(arg.strip())
        except ValueError:
            self.app.show_info("Usage: /fork [n]  (n = user turns to rewind)")
            return
        if n < 0:
            self.app.show_info("n must be non-negative")
            return

        cut_at = len(panel.messages)
        prefill: str | None = None
        if n > 0:
            user_indexes = [i for i, m in enumerate(panel.messages) if m.get("role") == "user"]
            if len(user_indexes) < n:
                self.app.show_info(f"Cannot rewind {n}: only {len(user_indexes)} user turns in history")
                return
            cut_at = user_indexes[-n]
            from .ui.modals import _message_text

            prefill = _message_text(panel.messages[cut_at])

        self._do_fork_at(cut_at, prefill=prefill)

    def forks(self, arg: str) -> None:
        """Run /forks — list children of the active session."""
        del arg
        panel = self.app.active_panel
        if not panel or not panel.session_id:
            self.app.show_info("Active session has no id yet (send a message first)")
            return
        children = list_forks(panel.session_id)
        if not children:
            self.app.show_info("No forks of this session")
            return
        lines = [f"[bold #7aa2f7]Forks of {panel.session_id}[/]"]
        lines.extend(f"  {sid}" for sid in children)
        lines.append("[dim]Open one with Ctrl+S.[/]")
        self.app.show_info("\n".join(lines))

    def on_fork_picked(self, result: tuple[int, str | None] | None) -> None:
        """Modal dismiss callback. result is (cut_at, prefill) or None."""
        if result is None:
            return
        cut_at, prefill = result
        self._do_fork_at(cut_at, prefill=prefill)

    def _do_fork_at(self, cut_at: int, *, prefill: str | None = None) -> None:
        """Create a fork of the active panel keeping messages[:cut_at]."""
        panel = self.app.active_panel
        if not panel:
            return
        if not 0 <= cut_at <= len(panel.messages):
            self.app.show_info(f"[#f7768e]Invalid fork point:[/] {cut_at}")
            return

        parent_id = panel.session_id
        new_id = f"{parent_id or 'chat'}-fork-{time.time_ns()}"
        ok = fork_session_copy(
            new_id=new_id,
            messages=panel.messages[:cut_at],
            parent_session_id=parent_id,
            forked_at_index=cut_at,
            working_dir=str(panel.working_dir),
        )
        if not ok:
            self.app.show_info(f"[#f7768e]Fork id collision:[/] {new_id}")
            return

        # Re-render the parent panel inline so its new BranchMarker shows up
        # without the user having to close and re-open the session.
        if parent_id:
            save_session(parent_id, panel.messages, working_dir=str(panel.working_dir))
            panel.load_session(parent_id)

        if len(self.app.panels) >= 4:
            self.app.refresh_sessions()
            self.app.show_info(f"[#9ece6a]Forked to[/] {new_id} [dim](panel limit reached; open with Ctrl+S)[/]")
            return

        self.app.notify(f"Forked at message {cut_at}: {new_id}", timeout=3.0)
        self.app.create_panel(initial_session_id=new_id, initial_input=prefill)
        self.app.refresh_sessions()
