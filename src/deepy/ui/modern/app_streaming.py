from __future__ import annotations

from textual.css.query import NoMatches

from deepy.input_suggestions import generate_input_suggestion, is_eligible_for_input_suggestion
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.multimodal import PromptImageAttachment
from deepy.llm.runner import RunSummary
from deepy.sessions import DeepySession
from deepy.format_tokens import format_stream_token_count_short as _format_stream_token_count_short
from deepy.ui.modern.app_helpers import _tool_output_diff_text
from deepy.ui.modern.app_patchable import resolve as _resolve
from deepy.ui.modern.app_state_proto import AppStateProto
from deepy.ui.modern.app_widgets import StreamEventMessage, TurnCompleteMessage, TurnFailedMessage
from deepy.ui.modern.render.diff import diff_view_from_tool_output
from deepy.ui.modern.render.transcript_items import (
    _is_local_command_tool_output,
    _raw_tool_call_event,
    _recoverable_tool_key,
)
from deepy.ui.modern.state import (
    add_assistant_delta,
    add_reasoning_delta,
    reset_turn_buffers,
    set_busy,
    set_pending_questions,
    set_session_id,
    set_usage,
)
from deepy.ui.modern.widgets import (
    DiffBlock,
    ErrorBlock,
    LocalCommandBlock,
    PromptPanel,
    ThinkingBlock,
    ToolBlock,
    UserBlock,
)
from deepy.ui.shared.render.message_view import parse_tool_output


class AppStreamingMixin(AppStateProto):
    async def run_model_turn(
        self,
        prompt: str,
        skill_names: list[str],
        image_attachments: list[PromptImageAttachment] | None = None,
    ) -> None:
        await self.mcp_runtime.connect()
        try:
            summary = await self.run_once(
                prompt,
                project_root=self.project_root,
                settings=self.settings,
                emit_event=lambda event: self.post_message(StreamEventMessage(event)),
                should_interrupt=lambda: self.state.interrupt_requested,
                session_id=self.state.session_id,
                skill_names=skill_names,
                background_tasks=self.background_tasks,
                mcp_runtime=self.mcp_runtime,
                audit_mode=self.audit_state,
                approval_resolver=self._tui_approval_resolver,
                image_attachments=image_attachments or [],
            )
        except Exception as exc:
            self.post_message(TurnFailedMessage(exc))
            return
        self.post_message(TurnCompleteMessage(summary))


    async def on_stream_event(self, message: StreamEventMessage) -> None:
        message.stop()
        await self._handle_stream_event(message.event)


    async def on_turn_complete(self, message: TurnCompleteMessage) -> None:
        message.stop()
        summary = message.summary
        await self._flush_assistant_block()
        self.state = set_session_id(self.state, summary.session_id)
        self._record_pending_session_cost_start(summary.session_id)
        self._refresh_status_session_entry()
        self.state = set_usage(self.state, summary.usage)
        self.state = set_pending_questions(self.state, summary.pending_questions)
        self.state = set_busy(self.state, False, "Idle")
        self.state = reset_turn_buffers(self.state)
        if summary.pending_questions:
            await self._show_pending_question(summary.pending_questions)
        self._update_status("Idle")
        self.run_worker(self._prepare_input_suggestion(summary), exclusive=False)


    async def on_turn_failed(self, message: TurnFailedMessage) -> None:
        message.stop()
        self._pending_session_cost_start = None
        self.state = set_busy(self.state, False, "Error")
        await self._append_block(ErrorBlock(str(message.error)))
        self._update_status("Error")


    async def _prepare_input_suggestion(self, summary: RunSummary) -> None:
        self._clear_input_suggestion()
        if not summary.session_id or summary.pending_questions:
            return
        try:
            session = DeepySession.open(self.project_root, summary.session_id)
            items = await session.get_items()
            if not is_eligible_for_input_suggestion(
                items,
                enabled=self.settings.ui.input_suggestions_enabled,
                has_pending_questions=bool(summary.pending_questions),
                turn_status=summary.status,
            ):
                return
            suggestion = await generate_input_suggestion(self.settings, items)
            if suggestion is None or self.state.busy or self.state.pending_questions:
                return
            session.record_input_suggestion_usage(
                suggestion.usage,
                model=suggestion.model,
                elapsed_ms=suggestion.elapsed_ms,
            )
            self.input_suggestions.set_suggestion(suggestion.text)
            panel = self.query_one(PromptPanel)
            panel.set_input_suggestion(suggestion.text)
        except Exception:
            return


    def _clear_input_suggestion(self) -> None:
        self.input_suggestions.dismiss()
        try:
            self.query_one(PromptPanel).clear_input_suggestion()
        except NoMatches:
            return


    def _record_stream_progress(self, text: str) -> None:
        self._stream_tokens += _resolve("estimate_tokens_for_text")(text)


    def _stream_status_text(self) -> str:
        return (
            f"↓ {_format_stream_token_count_short(self._stream_tokens)} tokens"
            if self._stream_tokens > 0
            else "Running"
        )


    async def _handle_stream_event(self, event: DeepyStreamEvent) -> None:
        if event.kind == "text_delta" and event.text:
            self._record_stream_progress(event.text)
            self.state = add_assistant_delta(self.state, event.text)
            await self._append_assistant_delta(event.text)
            self._update_status(self._stream_status_text())
            return
        if event.kind == "message" and event.text:
            if not self.state.assistant_buffer:
                self.state = add_assistant_delta(self.state, event.text)
                await self._append_assistant_delta(event.text)
            return
        if event.kind == "raw_response":
            if raw_tool_call := _raw_tool_call_event(event):
                await self._handle_stream_event(raw_tool_call)
                return
            if event.text:
                self._record_stream_progress(event.text)
                self._update_status(self._stream_status_text())
            return
        if event.kind == "reasoning_delta" and event.text:
            self._record_stream_progress(event.text)
            self.state = add_reasoning_delta(self.state, event.text)
            if self.settings.ui.view_mode == "full":
                if self._thinking_block is None:
                    self._thinking_block = ThinkingBlock(event.text)
                    await self._append_block(self._thinking_block)
                else:
                    anchored = self._transcript_is_anchored_now()
                    self._thinking_block.update_text(self._thinking_block.body + event.text)
                    self._scroll_transcript_to_end(force=anchored)
            self._update_status(self._stream_status_text())
            return
        if event.kind == "tool_call":
            self._thinking_block = None
            call_id = str(event.payload.get("call_id") or "")
            if call_id and call_id in self._completed_tool_call_ids:
                return
            tool_name = event.name or "tool"
            arguments = str(event.payload.get("arguments") or "")
            params = ToolBlock.from_call(tool_name, arguments, call_id=call_id).arguments
            retry_key = _recoverable_tool_key(tool_name, params)
            block = self._retryable_tool_blocks.pop(retry_key, None) if retry_key is not None else None
            existing_block = self._tool_blocks.get(call_id) if call_id else None
            if block is None and isinstance(existing_block, ToolBlock):
                block = existing_block
            if block is not None:
                block.call_id = call_id
                block.update_from_call(tool_name, arguments)
            else:
                block = ToolBlock.from_call(tool_name, arguments, call_id=call_id)
            if call_id:
                self._tool_blocks[call_id] = block
            if call_id and call_id in self._suppressed_approval_tool_call_ids:
                self._update_status(f"Tool {event.name or 'tool'} pending approval")
                return
            if block.parent is None:
                await self._append_block(block)
            self._close_active_assistant_if_followed_by(block)
            self._update_status(f"Tool {event.name or 'tool'}")
            return
        if event.kind == "tool_output":
            self._thinking_block = None
            call_id = str(event.payload.get("call_id") or "")
            if call_id:
                self._completed_tool_call_ids.add(call_id)
                self._suppressed_approval_tool_call_ids.discard(call_id)
            view = parse_tool_output(event.text)
            block = self._tool_blocks.get(call_id)
            if _is_local_command_tool_output(view):
                local_block = LocalCommandBlock.from_output(view, call_id=call_id)
                if call_id:
                    self._tool_blocks[call_id] = local_block
                await self._replace_or_append_block(block, local_block)
                self._close_active_assistant_if_followed_by(local_block)
                self._update_status(view.status.title())
                return
            diff_view = diff_view_from_tool_output(event.text, project_root=self.project_root)
            if diff_view is not None:
                diff_text = _tool_output_diff_text(event.text)
                if diff_text is not None and diff_text in self._approved_preflight_diffs:
                    self._approved_preflight_diffs.discard(diff_text)
                    if block is not None and block.parent is not None:
                        await block.remove()
                    self._update_status(view.status.title())
                    return
                diff_block = DiffBlock(
                    diff_view,
                    theme=self.settings.ui.theme,
                    width=max(40, self.size.width - 6),
                )
                await self._replace_or_prioritize_diff_block(block, diff_block)
                self._close_active_assistant_if_followed_by(diff_block)
                self._update_status(view.status.title())
                return
            if block is None:
                block = ToolBlock.from_output(view, call_id=call_id, project_root=self.project_root)
                if call_id:
                    self._tool_blocks[call_id] = block
                await self._append_block(block)
                self._close_active_assistant_if_followed_by(block)
            elif isinstance(block, ToolBlock):
                anchored = self._transcript_is_anchored_now()
                block.update_from_output(view, project_root=self.project_root)
                self._scroll_transcript_to_end(force=anchored)
                self._close_active_assistant_if_followed_by(block)
            else:
                return
            retry_key = _recoverable_tool_key(view.name, block.arguments)
            if view.status == "retryable" and retry_key is not None:
                self._retryable_tool_blocks[retry_key] = block
            elif view.ok is True and retry_key is not None:
                self._retryable_tool_blocks.pop(retry_key, None)
            if view.name == "todo_write":
                self._todo_text = block.output_body
                self._update_status(self.state.status)
            self._update_status(view.status.title())
            return
        if event.kind == "usage":
            self.state = set_usage(self.state, event.payload.get("usage"))
            return
        if event.kind == "status" and event.text:
            await self._append_block(UserBlock(event.text))
            self._update_status(event.text)


