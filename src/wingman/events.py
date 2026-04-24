"""Input and event handling for wingman.

Routes Textual events (key presses, paste, image drops, input changes,
form submissions) to the appropriate app actions. Methods here are
called directly from the ``WingmanApp`` event handlers, which must
remain on the App class for Textual dispatch.

"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING

from textual.widgets import Input

from .command_completion import get_hint_candidates
from .images import cache_image_immediately, is_image_path
from .sessions import save_session

if TYPE_CHECKING:
    from textual import events

    from .app import WingmanApp
    from .ui import ImageChip, MultilineInput


class EventHandler:
    """Handles input events and routes them to the appropriate actions.

    Attached to the app as ``self.events``.

    """

    def __init__(self, app: WingmanApp) -> None:
        self.app = app

    def on_descendant_focus(self, event) -> None:
        """Set panel as active when any of its descendants receives focus."""
        for i, panel in enumerate(self.app.panels):
            if panel in event.widget.ancestors_with_self:
                if i != self.app.active_panel_idx:
                    self.app.set_active_panel(i)
                break

    def on_click(self, event) -> None:
        """Focus input when clicking anywhere in the main area."""
        from textual.widgets import Button, ListView

        panel = self.app.active_panel
        if not panel:
            return
        if not isinstance(event.widget, (Button, Input, ListView)):
            from .ui import ImageChip, ToolApproval

            if isinstance(event.widget, (ImageChip, ToolApproval)):
                return
            approvals = list(panel.query("ToolApproval"))
            if approvals:
                approvals[0].focus()
            else:
                panel.get_input().focus()

    def on_paste(self, event: events.Paste) -> None:
        """Route paste events to the active input if not already focused there."""
        panel = self.app.active_panel
        if not panel:
            return
        input_widget = panel.get_input()
        if self.app.focused != input_widget and event.text:
            input_widget.focus()
            input_widget._on_paste(event)
            event.stop()

    def on_image_dropped(self, event: MultilineInput.ImageDropped) -> None:
        """Attach a dropped/pasted image."""
        panel = self.app.active_panel
        if not panel:
            return
        image_path = is_image_path(event.path)
        if not image_path:
            return
        if any(img.name == image_path.name for img in panel.pending_images):
            return
        cached = cache_image_immediately(image_path)
        if not cached:
            return
        panel.pending_images.append(cached)
        panel.refresh_image_chips()
        panel.get_hint().update("[dim]↑ to select images · backspace to remove[/]")
        self.app.update_status()

    def on_image_chip_removed(self, event: ImageChip.Removed) -> None:
        """Remove an image when its chip is deleted."""
        panel = self.app.active_panel
        if not panel or not (0 <= event.index < len(panel.pending_images)):
            return
        panel.pending_images.pop(event.index)
        panel.refresh_image_chips()
        self.app.update_status()
        if panel.pending_images:
            new_idx = min(event.index, len(panel.pending_images) - 1)

            def focus_chip():
                from .ui import ImageChip

                chips = list(panel.get_chips_container().query(ImageChip))
                if chips and new_idx < len(chips):
                    chips[new_idx].focus()

            self.app.call_after_refresh(focus_chip)
        else:
            panel.get_hint().update("")
            panel.get_input().focus()

    def on_image_chip_navigate(self, event: ImageChip.Navigate) -> None:
        """Handle chip arrow key navigation."""
        from .ui import ImageChip

        panel = self.app.active_panel
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
        from .ui import ImageChip

        if event.key == "escape" and len(self.app.screen_stack) == 1:
            panel = self.app.active_panel
            if panel and panel._generating:
                panel._cancel_requested = True
                panel._generating = False
                self.app.update_status()
                for thinking in panel.query("Thinking"):
                    with contextlib.suppress(Exception):
                        thinking.remove()
                for approval in panel.query("ToolApproval"):
                    with contextlib.suppress(Exception):
                        approval.remove()
                self.app.notify("Generation cancelled", severity="warning", timeout=2)
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

        panel = self.app.active_panel
        if not panel:
            return

        focused = self.app.focused

        if event.key == "up" and panel.pending_images:
            if focused and isinstance(focused, Input) and "panel-prompt" in focused.classes:
                chips = list(panel.get_chips_container().query(ImageChip))
                if chips:
                    event.prevent_default()
                    chips[-1].focus()

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

    def on_input_changed(self, event: Input.Changed) -> None:
        """Show command hints and auto-detect image paths."""
        from .ui import ChatPanel

        panel = None
        for ancestor in event.input.ancestors_with_self:
            if isinstance(ancestor, ChatPanel):
                panel = ancestor
                break
        if not panel:
            return
        hint = panel.get_hint()
        text = event.value

        text_lower = text.strip().strip("'\"").lower() if text else ""
        has_image_ext = any(
            text_lower.endswith(ext) or text_lower.endswith(ext.replace(".", "%2e"))
            for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
        )
        if text and has_image_ext:
            image_path = is_image_path(text)
            if image_path:
                if any(img.name == image_path.name for img in panel.pending_images):
                    event.input.clear()
                    return
                cached = cache_image_immediately(image_path)
                if cached:
                    event.input.clear()
                    panel.pending_images.append(cached)
                    panel.refresh_image_chips()
                    panel.get_hint().update("[dim]↑ to select images · backspace to remove[/]")
                    self.app.update_status()
                    return

        if text.startswith("/"):
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

    def on_submit(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        from .ui import Thinking

        panel = None
        for p in self.app.panels:
            if p.panel_id in event.input.id:
                panel = p
                break
        if not panel:
            return

        if panel._generating:
            self.app.notify("Wait for response to complete", severity="warning", timeout=2)
            return

        if panel != self.app.active_panel:
            self.app.set_active_panel(self.app.panels.index(panel))

        text = (
            event.input.get_submit_value().strip() if hasattr(event.input, "get_submit_value") else event.value.strip()
        )

        if not text and not panel.pending_images:
            return

        event.input.clear()
        panel.get_hint().update("")

        if text.startswith("/"):
            self.app.handle_command(text)
            return

        try:
            for child in panel.get_chat_container().children:
                if "panel-welcome" in child.classes:
                    child.remove()
                    break
        except Exception:
            pass

        if not panel.session_id:
            panel.session_id = f"chat-{int(time.time() * 1000)}"
            save_session(panel.session_id, [])
            self.app.refresh_sessions()
            self.app.update_status()

        images_to_send = panel.pending_images.copy()
        panel.pending_images = []
        panel.refresh_image_chips()

        if images_to_send:
            panel.add_image_message("user", text, images_to_send)
        else:
            panel.add_message("user", text)

        save_session(panel.session_id, panel.messages)

        chat = panel.get_chat_container()
        thinking = Thinking(id="thinking")
        chat.mount(thinking)
        panel.get_scroll_container().scroll_end(animate=False)

        self.app.streaming.send_message(panel, text, thinking, images_to_send)
