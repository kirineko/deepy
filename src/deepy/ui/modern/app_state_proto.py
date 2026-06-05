from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from deepy.audit import ApprovalDecision, AuditModeState, PendingApproval
from deepy.background_tasks import BackgroundTaskManager
from deepy.config import Settings
from deepy.input_suggestions import InputSuggestionController
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.multimodal import PromptImageAttachment
from deepy.llm.runner import RunSummary
from deepy.mcp import DeepyMcpRuntime
from deepy.sessions import SessionEntry
from deepy.ui.modern.screens import Choice
from deepy.ui.modern.state import TuiController, TuiState
from deepy.ui.modern.widgets import AssistantBlock, LocalCommandBlock, ThinkingBlock, ToolBlock
from deepy.ui.shared.input.image_input import ImageAttachmentController
from textual.app import App
from textual.reactive import var
from textual.widget import Widget


RunOnce = Callable[..., Coroutine[Any, Any, RunSummary]]


class AppStateProto(App[None]):
    settings: Settings
    project_root: Path
    run_once: RunOnce
    guide_missing_config: bool
    controller: TuiController
    audit_state: AuditModeState
    input_suggestions: InputSuggestionController
    image_attachments: ImageAttachmentController
    state: var[TuiState]
    _assistant_block: AssistantBlock | None
    _assistant_rendered_text: str
    _thinking_block: ThinkingBlock | None
    _tool_blocks: dict[str, ToolBlock | LocalCommandBlock]
    _retryable_tool_blocks: dict[tuple[str, str], ToolBlock]
    _focused_block_index: int
    _pending_question_answers: OrderedDict[str, str]
    _new_output_available: bool
    _todo_text: str
    _stream_tokens: int
    _local_command_sequence: int
    _status_session_entry: SessionEntry | None
    _status_session_entry_id: str | None
    _status_session_entry_loaded: bool
    background_tasks: BackgroundTaskManager
    mcp_runtime: DeepyMcpRuntime
    exit_summary_text: str | None
    _pending_session_cost_start: dict[str, Any] | None
    _pending_audit_decision: asyncio.Future[str] | None
    _pending_inline_choice: asyncio.Future[str | None] | None
    _active_interaction_block: Widget | None
    _approved_preflight_diffs: set[str]
    _suppressed_approval_tool_call_ids: set[str]
    _completed_tool_call_ids: set[str]

    # Cross-mixin method stubs for static typing (implemented on concrete mixins).
    async def _append_block(self, block: Any) -> None:
        raise NotImplementedError

    async def _replace_or_append_block(self, old_block: Widget | None, new_block: Widget) -> None:
        raise NotImplementedError

    async def _replace_or_prioritize_diff_block(
        self,
        old_block: Widget | None,
        new_block: Widget,
    ) -> None:
        raise NotImplementedError

    async def _clear_transcript(self) -> None:
        raise NotImplementedError

    async def _restore_transcript(self, session_id: str) -> None:
        raise NotImplementedError

    async def _flush_assistant_block(self) -> None:
        raise NotImplementedError

    async def _append_assistant_delta(self, text: str) -> None:
        raise NotImplementedError

    def _close_active_assistant_if_followed_by(self, block: Widget) -> None:
        raise NotImplementedError

    def _scroll_transcript_to_end(self, *, force: bool = False) -> None:
        raise NotImplementedError

    def _transcript_is_anchored_now(self) -> bool:
        raise NotImplementedError

    async def run_model_turn(
        self,
        prompt: str,
        skill_names: list[str],
        image_attachments: list[PromptImageAttachment] | None = None,
    ) -> None:
        raise NotImplementedError

    def _clear_input_suggestion(self) -> None:
        raise NotImplementedError

    async def _handle_stream_event(self, event: DeepyStreamEvent) -> None:
        raise NotImplementedError

    def _update_status(self, status: str) -> None:
        raise NotImplementedError

    def _set_status_bar(self, status: str) -> None:
        raise NotImplementedError

    def _refresh_status_session_entry(self) -> None:
        raise NotImplementedError

    def _record_pending_session_cost_start(self, session_id: str | None) -> None:
        raise NotImplementedError

    async def _handle_skills_command(self, argument: str) -> bool:
        raise NotImplementedError

    async def _stop_background_tasks(self, selection: str = "") -> None:
        raise NotImplementedError

    async def _new_session(self) -> None:
        raise NotImplementedError

    async def _show_sessions(self) -> None:
        raise NotImplementedError

    async def _resume_session(self, session_id: str | None) -> None:
        raise NotImplementedError

    async def _compact_session(self, focus_instruction: str | None) -> None:
        raise NotImplementedError

    async def _tui_approval_resolver(self, pending: list[PendingApproval]) -> list[ApprovalDecision]:
        raise NotImplementedError

    async def _choose_inline(
        self,
        title: str,
        choices: list[Choice],
        *,
        restore_prompt_focus: bool = True,
    ) -> str | None:
        raise NotImplementedError

    async def _show_pending_question(self, pending_questions: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def _apply_theme(self) -> None:
        raise NotImplementedError

    def _refresh_prompt_commands(self) -> None:
        raise NotImplementedError
