from __future__ import annotations

import asyncio
from typing import Any

from textual.css.query import NoMatches
from textual.containers import Vertical
from textual.widget import Widget

from deepy.audit import ApprovalDecision, PendingApproval
from deepy.ui.modern.app_helpers import _tool_output_diff_text
from deepy.ui.modern.app_state_proto import AppStateProto
from deepy.ui.modern.render.diff import diff_view_from_tool_output
from deepy.ui.modern.screens import Choice
from deepy.ui.modern.state import reset_turn_buffers, set_busy, set_pending_questions
from deepy.ui.modern.widgets import (
    AuditDecisionBlock,
    DiffBlock,
    InfoBlock,
    InlineChoiceBlock,
    InlineChoiceOption,
    LocalCommandBlock,
    PromptTextArea,
    QuestionBlock,
    ToolBlock,
    UserBlock,
)
from deepy.ui.shared.input.ask_user_question import (
    format_ask_user_question_answers,
    format_ask_user_question_decline,
    normalize_questions,
)
from deepy.utils import json as json_utils


class AppInteractionMixin(AppStateProto):
    async def _tui_approval_resolver(self, pending: list[PendingApproval]) -> list[ApprovalDecision]:
        decisions: list[ApprovalDecision] = []
        for item in pending:
            if item.call_id:
                self._suppressed_approval_tool_call_ids.add(item.call_id)
            await self._detach_pending_approval_tool_block(item)
            proposed_diff = await self._append_preflight_diff(item)
            choice = await self._show_inline_audit_decision(item)
            approved = choice == "approve"
            if proposed_diff and approved:
                self._approved_preflight_diffs.add(proposed_diff)
            elif proposed_diff:
                await self._append_block(InfoBlock("Proposed change rejected."))
            elif approved:
                await self._append_pending_approval_tool_block(item)
                if item.call_id:
                    self._suppressed_approval_tool_call_ids.discard(item.call_id)
            decisions.append(
                ApprovalDecision(
                    outcome="approve" if approved else "reject",
                    rejection_message=None
                    if approved
                    else "Tool execution was rejected by the user audit approval decision.",
                )
            )
        return decisions


    async def _detach_pending_approval_tool_block(self, item: PendingApproval) -> None:
        block = self._approval_tool_block(item)
        if block is None or not isinstance(block.parent, Widget):
            return
        await block.remove()


    async def _append_pending_approval_tool_block(self, item: PendingApproval) -> None:
        if not item.call_id:
            return
        existing = self._tool_blocks.get(item.call_id)
        if isinstance(existing, LocalCommandBlock):
            return
        block = existing if isinstance(existing, ToolBlock) else None
        if block is None:
            block = ToolBlock.from_call(item.tool_name, item.arguments, call_id=item.call_id)
        self._tool_blocks[item.call_id] = block
        if block.parent is None:
            await self._append_block(block)


    def _approval_tool_block(self, item: PendingApproval) -> ToolBlock | None:
        if item.call_id:
            block = self._tool_blocks.get(item.call_id)
            return block if isinstance(block, ToolBlock) else None
        expected_arguments = ToolBlock.from_call(item.tool_name, item.arguments, call_id="").arguments
        for block in self._tool_blocks.values():
            if (
                isinstance(block, ToolBlock)
                and block.tool_name == item.tool_name
                and block.arguments == expected_arguments
            ):
                return block
        return None


    async def _append_preflight_diff(self, item: PendingApproval) -> str | None:
        if item.preflight is None:
            return None
        output = json_utils.dumps(item.preflight)
        diff_text = _tool_output_diff_text(output)
        diff_view = diff_view_from_tool_output(output, project_root=self.project_root)
        if diff_text is None or diff_view is None:
            return None
        await self._append_block(
            DiffBlock(
                diff_view,
                theme=self.settings.ui.theme,
                width=max(40, self.size.width - 6),
            )
        )
        return diff_text


    async def _show_inline_audit_decision(self, item: PendingApproval) -> str:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending_audit_decision = future
        block = AuditDecisionBlock(
            item,
            project_root=self.project_root,
            width=max(40, self.size.width - 6),
        )
        await self._show_interaction_block(block)
        try:
            return await future
        finally:
            if self._pending_audit_decision is future:
                self._pending_audit_decision = None
            await self._clear_interaction_sheet()
            self.call_after_refresh(self.query_one("#prompt-input", PromptTextArea).focus)


    def on_audit_decision(self, message: AuditDecisionBlock.Decided) -> None:
        message.stop()
        future = self._pending_audit_decision
        if future is not None and not future.done():
            future.set_result(message.outcome)


    async def _choose_inline(
        self,
        title: str,
        choices: list[Choice],
        *,
        restore_prompt_focus: bool = True,
    ) -> str | None:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str | None] = loop.create_future()
        self._pending_inline_choice = future
        block = InlineChoiceBlock(
            title,
            [
                InlineChoiceOption(choice.label, choice.value, choice.description)
                for choice in choices
            ],
        )
        await self._show_interaction_block(block)
        try:
            return await future
        finally:
            if self._pending_inline_choice is future:
                self._pending_inline_choice = None
            await self._clear_interaction_sheet()
            if restore_prompt_focus:
                try:
                    prompt = self.query_one("#prompt-input", PromptTextArea)
                except NoMatches:
                    return
                self.call_after_refresh(prompt.focus)


    def on_inline_choice(self, message: InlineChoiceBlock.Chosen) -> None:
        message.stop()
        future = self._pending_inline_choice
        if future is not None and not future.done():
            future.set_result(message.value)


    async def on_question_answered(self, message: QuestionBlock.Answered) -> None:
        message.stop()
        self._pending_question_answers[message.question] = message.answer
        questions = normalize_questions(self.state.pending_questions)
        if len(self._pending_question_answers) < len(questions):
            await self._show_interaction_block(QuestionBlock(questions[len(self._pending_question_answers)]))
            return
        await self._clear_interaction_sheet()
        continuation = format_ask_user_question_answers(self._pending_question_answers)
        self._pending_question_answers.clear()
        self.state = set_pending_questions(self.state, [])
        self.state = set_busy(reset_turn_buffers(self.state), True, "Running")
        self._assistant_block = None
        self._assistant_rendered_text = ""
        self._thinking_block = None
        self._stream_tokens = 0
        self._tool_blocks.clear()
        self._suppressed_approval_tool_call_ids.clear()
        self._completed_tool_call_ids.clear()
        self._update_status("Running")
        self.run_model_turn(continuation, list(self.controller.loaded_skill_names))


    async def _show_pending_question(self, pending_questions: list[dict[str, Any]]) -> None:
        questions = normalize_questions(pending_questions)
        if not questions:
            self._update_status(f"Questions pending: {len(pending_questions)}")
            return
        self._pending_question_answers.clear()
        await self._show_interaction_block(QuestionBlock(questions[0]))


    async def _show_interaction_block(self, block: Widget) -> None:
        sheet = self.query_one("#interaction-sheet", Vertical)
        await sheet.remove_children()
        sheet.display = True
        self._active_interaction_block = block
        self._set_prompt_interaction_locked(True)
        await sheet.mount(block)
        self._focus_interaction_block(block)
        self._scroll_transcript_to_end(force=True)
        self.call_after_refresh(lambda: self._scroll_transcript_to_end(force=True))


    async def _clear_interaction_sheet(self) -> None:
        try:
            sheet = self.query_one("#interaction-sheet", Vertical)
        except NoMatches:
            return
        await sheet.remove_children()
        sheet.display = False
        self._active_interaction_block = None
        self._set_prompt_interaction_locked(False)


    def _set_prompt_interaction_locked(self, locked: bool) -> None:
        try:
            prompt = self.query_one("#prompt-input", PromptTextArea)
        except NoMatches:
            return
        prompt.disabled = locked


    def _refocus_active_interaction(self) -> None:
        block = self._active_interaction_block
        if block is not None:
            self._focus_interaction_block(block)


    def _focus_interaction_block(self, block: Widget) -> None:
        def focus_target() -> None:
            for selector in (
                "#question-custom",
                "#inline-choice-options",
                "#audit-decision-options",
                "#question-options",
            ):
                try:
                    target = block.query_one(selector)
                except NoMatches:
                    continue
                if target.display is False:
                    continue
                target.focus()
                return
            block.focus()

        self.call_after_refresh(focus_target)


    def _cancel_active_interaction(self) -> bool:
        block = self._active_interaction_block
        if isinstance(block, AuditDecisionBlock):
            block.action_reject()
            return True
        if isinstance(block, QuestionBlock):
            block.action_cancel()
            return True
        if isinstance(block, InlineChoiceBlock):
            block.action_cancel()
            return True
        return False


    async def on_question_cancelled(self, message: QuestionBlock.Cancelled) -> None:
        message.stop()
        await self._clear_interaction_sheet()
        self._pending_question_answers.clear()
        self.state = set_pending_questions(self.state, [])
        await self._append_block(UserBlock(format_ask_user_question_decline()))
        self._update_status("Question cancelled")


