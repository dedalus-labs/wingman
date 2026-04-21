"""Streaming controller for wingman.

Owns the API call lifecycle: building messages, streaming responses,
handling tool calls, compaction, and error recovery.

"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

from .checkpoints import set_current_session
from .config import load_instructions
from .images import CachedImage, create_image_message_from_cache
from .memory import load_memory
from .sessions import save_session
from .tools import CODING_SYSTEM_PROMPT, add_text_segment, clear_segments, create_tools, get_segments

if TYPE_CHECKING:
    from .app import WingmanApp
    from .ui import ChatPanel, StreamingText, Thinking


class StreamingController:
    """Manages the send-message -> stream -> save lifecycle.

    Attached to the app as ``self.streaming``.

    """

    def __init__(self, app: WingmanApp) -> None:
        self.app = app

    async def send_message(
        self,
        panel: ChatPanel,
        text: str,
        thinking: Thinking,
        images: list[CachedImage] | None = None,
    ) -> None:
        """Stream a model response for the given user message.

        Handles message building, streaming, segment tracking,
        error recovery, and auto-compaction.

        Args:
            panel: Active chat panel.
            text: User message text.
            thinking: Thinking spinner widget (removed on completion).
            images: Optional attached images.

        """
        from .ui import APIKeyScreen

        if self.app.runner is None:
            thinking.remove()
            panel.add_message("assistant", "Please enter your API key first.")
            self.app.push_screen(APIKeyScreen(), self.app.on_api_key_entered)
            return

        try:
            messages = self.build_messages(panel, text, images)
            kwargs = self.build_kwargs(panel, messages)

            set_current_session(panel.session_id)
            clear_segments(panel.panel_id)
            chat = panel.get_chat_container()

            streaming_widget: StreamingText | None = None
            widget_id = int(time.time() * 1000)

            panel._generating = True
            panel._cancel_requested = False
            was_cancelled = False
            self.app.update_status()

            try:
                stream = self.app.runner.run(**kwargs)

                if hasattr(stream, "__aenter__") and not hasattr(stream, "__aiter__"):
                    streaming_widget, was_cancelled = await self.stream_events(
                        stream,
                        panel,
                        chat,
                        thinking,
                        streaming_widget,
                        widget_id,
                    )
                else:
                    streaming_widget, was_cancelled = await self.stream_chunks(
                        stream,
                        panel,
                        chat,
                        thinking,
                        streaming_widget,
                        widget_id,
                    )
            finally:
                panel._generating = False
                set_current_session(None)

            if streaming_widget is not None:
                streaming_widget.mark_complete()
            self.app.update_status()

            with contextlib.suppress(Exception):
                thinking.remove()

            # Remove transient skill prompts before saving
            panel.messages = [m for m in panel.messages if not m.get("_skill")]

            segments = get_segments(panel.panel_id)
            if segments:
                panel.messages.append({"role": "assistant", "segments": segments})
                save_session(panel.session_id, panel.messages)
            elif not was_cancelled:
                self.app.show_info("[#e0af68]Response ended with no content[/]\n[dim]Use /bug to report this issue[/]")

            self.app.update_status()
            await self.app.compaction.check_auto(panel)

        except asyncio.TimeoutError:
            self.handle_error(panel, thinking, "[#f7768e]Request timed out[/]")

        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                self.handle_error(panel, thinking, "[#f7768e]Request timed out[/]")
            elif "cancelled" not in error_msg.lower():
                self.handle_error(
                    panel,
                    thinking,
                    None,
                    user_message=f"Error: {error_msg}\n\nUse /bug to report this issue.",
                )
            else:
                self.handle_error(panel, thinking, None)

    # --- Message building ---

    def build_messages(
        self,
        panel: ChatPanel,
        text: str,
        images: list[CachedImage] | None = None,
    ) -> list[dict]:
        """Convert panel history into API-ready messages.

        Args:
            panel: Chat panel with message history.
            text: Current user message.
            images: Optional attached images.

        Returns:
            List of message dicts ready for the API.

        """
        messages = []
        for msg in panel.messages:
            if msg.get("segments"):
                content_parts = []
                for seg in msg["segments"]:
                    if seg.get("type") == "text":
                        content_parts.append(seg["content"])
                    elif seg.get("type") == "tool":
                        cmd = seg.get("command", "")
                        output = seg.get("output", "")
                        content_parts.append(f"\n[Tool: {cmd}]\n{output}\n")
                messages.append({"role": msg["role"], "content": "".join(content_parts)})
            else:
                clean = {k: v for k, v in msg.items() if not k.startswith("_")}
                messages.append(clean)

        if images and messages and messages[-1].get("role") == "user":
            messages[-1] = create_image_message_from_cache(text, images)

        if self.app.coding_mode:
            system_content = CODING_SYSTEM_PROMPT.format(cwd=panel.working_dir)
            instructions = load_instructions(panel.working_dir)
            if instructions:
                system_content += f"\n\n{instructions}"
            memory = load_memory()
            if memory.entries:
                memory_text = "\n".join(e.content for e in memory.entries)
                system_content += f"\n\n## Project Memory\n{memory_text}"
            messages = [{"role": "system", "content": system_content}] + messages

        return messages

    def build_kwargs(self, panel: ChatPanel, messages: list[dict]) -> dict:
        """Build the API call keyword arguments.

        Args:
            panel: Chat panel for context (MCP, tools, model).
            messages: Prepared message list.

        Returns:
            Dict of kwargs for runner.run().

        """
        kwargs: dict = {
            "messages": messages,
            "model": self.app.model,
            "stream": True,
        }
        if panel.mcp_servers:
            kwargs["mcp_servers"] = panel.mcp_servers
        if self.app.coding_mode:
            kwargs["tools"] = create_tools(panel.working_dir, panel.panel_id, panel.session_id)
        return kwargs

    # --- Stream handlers ---

    async def stream_events(
        self,
        stream,
        panel,
        chat,
        thinking,
        streaming_widget,
        widget_id,
    ) -> tuple[StreamingText | None, bool]:
        """Handle event-style streaming (e.g., Gemini).

        Returns:
            (streaming_widget, was_cancelled) tuple.

        """
        from .ui import StreamingText

        async with stream as event_stream:
            async for event in event_stream:
                if panel._cancel_requested:
                    return streaming_widget, True
                if hasattr(event, "type") and event.type == "content.delta":
                    content = getattr(event, "delta", None)
                    if content:
                        if streaming_widget is None:
                            widget_id += 1
                            streaming_widget = StreamingText(id=f"streaming-{widget_id}")
                            try:
                                chat.mount(streaming_widget, before=thinking)
                            except Exception:
                                return streaming_widget, True
                        add_text_segment(content, panel.panel_id)
                        streaming_widget.append_text(content)
                        panel.get_scroll_container().scroll_end(animate=False)
                        await asyncio.sleep(0)
        return streaming_widget, False

    async def stream_chunks(
        self,
        stream,
        panel,
        chat,
        thinking,
        streaming_widget,
        widget_id,
    ) -> tuple[StreamingText | None, bool]:
        """Handle chunk-style streaming (OpenAI-compatible).

        Returns:
            (streaming_widget, was_cancelled) tuple.

        """
        from .ui import StreamingText

        async for chunk in stream:
            if panel._cancel_requested:
                return streaming_widget, True
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "tool_calls") and delta.tool_calls and streaming_widget is not None:
                    streaming_widget.mark_complete()
                    streaming_widget = None
                if hasattr(delta, "content") and delta.content:
                    if streaming_widget is None:
                        widget_id += 1
                        streaming_widget = StreamingText(id=f"streaming-{widget_id}")
                        try:
                            chat.mount(streaming_widget, before=thinking)
                        except Exception:
                            return streaming_widget, True
                    add_text_segment(delta.content, panel.panel_id)
                    streaming_widget.append_text(delta.content)
                    panel.get_scroll_container().scroll_end(animate=False)
                    await asyncio.sleep(0)
        return streaming_widget, False

    # --- Error handling ---

    def handle_error(
        self,
        panel: ChatPanel,
        thinking: Thinking,
        info_message: str | None,
        user_message: str | None = None,
    ) -> None:
        """Clean up after a streaming error.

        Args:
            panel: Chat panel to clean up.
            thinking: Thinking spinner to remove.
            info_message: Rich-markup status message (shown via show_info).
            user_message: Plain-text message added to chat as assistant.

        """
        with contextlib.suppress(Exception):
            thinking.remove()
        for sw in self.app.query("StreamingText"):
            with contextlib.suppress(Exception):
                sw.remove()
        # Clean up transient skill prompts
        panel.messages = [m for m in panel.messages if not m.get("_skill")]
        segments = get_segments(panel.panel_id)
        if segments:
            panel.messages.append({"role": "assistant", "segments": segments})
            save_session(panel.session_id, panel.messages)
        elif panel.messages and panel.messages[-1].get("role") == "user":
            panel.messages.pop()
        if info_message:
            self.app.show_info(info_message)
        elif user_message:
            panel.add_message("assistant", user_message)
