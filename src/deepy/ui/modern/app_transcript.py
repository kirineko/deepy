from __future__ import annotations

from typing import Any

from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.widget import MountError, Widget

from deepy.ui.modern.app_state_proto import AppStateProto
from deepy.sessions import DeepySession
from deepy.ui.modern.app_helpers import _widget_appears_before
from deepy.ui.modern.render.transcript_items import (
    _chat_tool_calls,
    _history_tool_output_event,
    _item_text,
    _reasoning_text,
)
from deepy.ui.modern.widgets import (
    AssistantBlock,
    ErrorBlock,
    InfoBlock,
    ThinkingBlock,
    UserBlock,
)
from deepy.ui.shared.session.session_transcript import (
    history_tool_call_event as _history_tool_call_event,
    item_type as _item_type,
    role as _role,
)


class AppTranscriptMixin(AppStateProto):
    async def _append_block(self, block: Any) -> None:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return
        if not transcript.is_attached:
            return
        anchored = self._transcript_is_anchored(transcript)
        try:
            await transcript.mount(block)
        except MountError:
            return
        self._scroll_transcript_to_end(force=anchored)


    async def _replace_or_append_block(self, old_block: Widget | None, new_block: Widget) -> None:
        if old_block is None or not isinstance(old_block.parent, Widget):
            await self._append_block(new_block)
            return
        transcript = old_block.parent
        anchored = self._transcript_is_anchored_now()
        try:
            await transcript.mount(new_block, before=old_block)
        except MountError:
            await self._append_block(new_block)
            return
        await old_block.remove()
        self._scroll_transcript_to_end(force=anchored)


    async def _replace_or_prioritize_diff_block(
        self,
        old_block: Widget | None,
        new_block: Widget,
    ) -> None:
        assistant_block = self._assistant_block
        if assistant_block is not None and isinstance(assistant_block.parent, Widget):
            if old_block is None or not _widget_appears_before(old_block, assistant_block):
                await self._insert_block_before(assistant_block, new_block)
                if old_block is not None and isinstance(old_block.parent, Widget):
                    await old_block.remove()
                return
        await self._replace_or_append_block(old_block, new_block)


    async def _insert_block_before(self, anchor: Widget, block: Widget) -> None:
        parent = anchor.parent
        if not isinstance(parent, Widget):
            await self._append_block(block)
            return
        anchored = self._transcript_is_anchored_now()
        try:
            await parent.mount(block, before=anchor)
        except MountError:
            await self._append_block(block)
            return
        self._scroll_transcript_to_end(force=anchored)


    async def _clear_transcript(self) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        await transcript.remove_children()
        self._assistant_block = None
        self._assistant_rendered_text = ""
        self._thinking_block = None
        self._tool_blocks.clear()
        self._suppressed_approval_tool_call_ids.clear()
        self._completed_tool_call_ids.clear()
        self._focused_block_index = -1


    async def _restore_transcript(self, session_id: str) -> None:
        await self._clear_transcript()
        session = DeepySession.open(self.project_root, session_id)
        try:
            items = await session.get_items(limit=80)
        except Exception as exc:
            await self._append_block(ErrorBlock(f"Failed to restore session: {exc}"))
            return
        await self._append_block(InfoBlock(f"Resumed session: {session_id}"))
        for item in items:
            await self._restore_transcript_item(item)


    async def _restore_transcript_item(self, item: dict[str, Any]) -> None:
        item_type = _item_type(item)
        role = _role(item)

        if item_type == "reasoning":
            text = _reasoning_text(item)
            if text.strip() and self.settings.ui.view_mode == "full":
                await self._append_block(ThinkingBlock(text))
            return

        if item_type == "function_call":
            await self._handle_stream_event(_history_tool_call_event(item))
            return

        if item_type == "function_call_output" or role == "tool":
            await self._handle_stream_event(_history_tool_output_event(item))
            return

        if role == "user":
            content = _item_text(item.get("content", item.get("output", "")))
            if content:
                await self._append_block(UserBlock(content))
            return

        if role == "assistant":
            content = _item_text(item.get("content", item.get("output", "")))
            if content.strip():
                await self._append_block(AssistantBlock(content))
            for tool_call in _chat_tool_calls(item):
                await self._handle_stream_event(_history_tool_call_event(tool_call))
            return

        content = _item_text(item.get("content", item.get("output", item.get("text", ""))))
        if content:
            await self._append_block(InfoBlock(content))


    async def _flush_assistant_block(self) -> None:
        if not self.state.assistant_buffer:
            return
        remaining = self.state.assistant_buffer[len(self._assistant_rendered_text) :]
        if remaining:
            await self._append_assistant_delta(remaining)
        if self._assistant_block is None:
            return
        self._assistant_block.set_active(False)


    async def _append_assistant_delta(self, text: str) -> None:
        if not text:
            return
        if self._assistant_block is None:
            self._assistant_block = AssistantBlock(text, active=True)
            await self._append_block(self._assistant_block)
        else:
            anchored = self._transcript_is_anchored_now()
            self._assistant_block.set_active(True)
            await self._assistant_block.update_markdown(self._assistant_block.markdown + text)
            self._scroll_transcript_to_end(force=anchored)
        self._assistant_rendered_text += text


    def _close_active_assistant_if_followed_by(self, block: Widget) -> None:
        assistant = self._assistant_block
        if assistant is None:
            return
        if not isinstance(assistant.parent, Widget) or assistant.parent is not block.parent:
            return
        if not _widget_appears_before(assistant, block):
            return
        assistant.set_active(False)
        self._assistant_block = None
        self._scroll_transcript_to_end(force=self._transcript_is_anchored_now())


    def _scroll_transcript_to_end(self, *, force: bool = False) -> None:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return
        if not force and not self._transcript_is_anchored(transcript):
            self._new_output_available = True
            self._set_status_bar("New output ↓")
            return
        self._new_output_available = False
        transcript.scroll_end(animate=False, force=True, x_axis=False)
        self.call_after_refresh(self._scroll_transcript_to_end_now)
        self.set_timer(0.05, self._scroll_transcript_to_end_now)


    def _scroll_transcript_to_end_now(self) -> None:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return
        transcript.scroll_end(animate=False, force=True, immediate=True, x_axis=False)


    def _transcript_is_anchored(self, transcript: VerticalScroll) -> bool:
        return transcript.scroll_y >= max(0, transcript.max_scroll_y - 1)


    def _transcript_is_anchored_now(self) -> bool:
        try:
            transcript = self.query_one("#transcript", VerticalScroll)
        except NoMatches:
            return True
        return self._transcript_is_anchored(transcript)


