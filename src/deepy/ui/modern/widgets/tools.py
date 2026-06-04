"""Tool-call and local-command transcript blocks for the Modern UI."""

from __future__ import annotations

import contextlib
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Label, Static

from deepy.ui.modern.render.tool_format import (
    _is_subagent_tool_name,
    _local_command_meta_body,
    _local_command_output_body,
    _local_command_title,
    _subagent_details,
    _subagent_parameters,
    _tool_arguments_body,
    _tool_output_body,
    _tool_output_details,
    _tool_output_renderable,
    _tool_output_title,
    _tool_output_visible,
    _tool_title_name,
)
from deepy.ui.modern.render.transcript import transcript_display
from deepy.ui.modern.widgets.blocks import TranscriptBlock
from deepy.ui.shared.render.message_view import ToolOutputView


class ToolBlock(TranscriptBlock):
    def __init__(
        self,
        label: str,
        body: str = "",
        *,
        call_id: str = "",
        arguments: str = "",
        details: str = "",
        waiting_for_user: bool = False,
        tool_name: str = "",
        retryable: bool = False,
        recovered_from_retry: bool = False,
    ) -> None:
        classes = "tool-block todo-block" if tool_name == "todo_write" else transcript_display("tool").css_class
        if _is_subagent_tool_name(tool_name):
            classes += " subagent-block"
        if retryable:
            classes += " -retryable"
        super().__init__(label, body, classes=classes, kind="tool")
        self.call_id = call_id
        self.arguments = arguments.strip()
        self.details = details.strip()
        self.output_body = body.strip()
        self.body = ""
        self.waiting_for_user = waiting_for_user
        self.tool_name = tool_name
        self.retryable = retryable
        self.recovered_from_retry = recovered_from_retry
        self.status_state = "retryable" if retryable else "waiting" if waiting_for_user else "running"
        self._sync_status_classes()

    @classmethod
    def from_call(cls, name: str, arguments: str, *, call_id: str) -> ToolBlock:
        display_name = _tool_title_name(name or "tool")
        params = _tool_arguments_body(name or "tool", arguments)
        title = f"{display_name} running"
        if name == "shell" and params:
            title = f"{title} - {params}"
        details = _subagent_details(params, "") if _is_subagent_tool_name(name) else ""
        body = (
            "Waiting for user input."
            if name == "AskUserQuestion"
            else f"Parameters\n  {params}"
            if params
            else "Running"
        )
        return cls(
            title,
            body,
            call_id=call_id,
            arguments=params,
            details=details,
            tool_name=name or "tool",
        )

    @classmethod
    def from_output(
        cls,
        view: ToolOutputView,
        *,
        call_id: str = "",
        project_root: Path | None = None,
    ) -> ToolBlock:
        body = _tool_output_body(view)
        return cls(
            _tool_output_title(view, project_root=project_root),
            body,
            call_id=call_id,
            details=_tool_output_details(view),
            waiting_for_user=view.await_user_response,
            tool_name=view.name,
            retryable=view.status == "retryable",
        )

    def update_from_call(self, name: str, arguments: str) -> None:
        display_name = _tool_title_name(name or "tool")
        params = _tool_arguments_body(name or "tool", arguments)
        self.tool_name = name or "tool"
        self.arguments = params
        self.title = f"{display_name} running"
        if self.tool_name == "shell" and params:
            self.title = f"{self.title} - {params}"
        self.output_body = "Running"
        self.body = ""
        self.details = _subagent_details(params, "") if _is_subagent_tool_name(self.tool_name) else ""
        self.waiting_for_user = False
        self.retryable = False
        self.recovered_from_retry = True
        self.status_state = "running"
        self.query_one(".tool-summary", Static).update(self.title)
        self._update_visible_output()
        details = self.query_one(".tool-details", Static)
        details.update(self.details)
        details.display = self._details_visible()
        self.set_class(False, "-waiting")
        self.set_class(False, "-retryable")
        self._sync_status_classes()

    def update_from_output(self, view: ToolOutputView, *, project_root: Path | None = None) -> None:
        self.tool_name = view.name
        self.title = _tool_output_title(
            view,
            project_root=project_root,
            fallback_command=self.arguments,
        )
        output_body = _tool_output_body(view)
        self.output_body = output_body
        self.details = (
            _subagent_details(self.arguments, output_body)
            if _is_subagent_tool_name(view.name)
            else _tool_output_details(view)
        )
        self.waiting_for_user = view.await_user_response
        self.retryable = view.status == "retryable"
        self.status_state = "waiting" if self.waiting_for_user else view.status
        self.body = ""
        self.query_one(".tool-summary", Static).update(self.title)
        self._update_visible_output()
        details = self.query_one(".tool-details", Static)
        details.update(self.details)
        details.display = self._details_visible()
        self.set_class(self.waiting_for_user, "-waiting")
        self.set_class(self.retryable, "-retryable")
        self._sync_status_classes()
        self.set_class(view.name == "todo_write", "todo-block")
        self.set_class(_is_subagent_tool_name(view.name), "subagent-block")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="role-line tool-role-line"):
            yield Label(self.display_model.label, classes="block-title role-marker tool-marker")
            yield Static(self.title, classes="block-body tool-summary")
        params = Static(_subagent_parameters(self.arguments), classes="block-body subagent-parameters")
        params.display = self._subagent_parameters_visible()
        yield params
        visible_output = _tool_output_visible(self.tool_name, self.output_body)
        output = Static(
            _tool_output_renderable(self.tool_name, self.output_body) if visible_output else "",
            classes="block-body tool-output",
        )
        output.display = visible_output
        yield output
        detail = Static(self.details, classes="tool-details")
        detail.display = False
        yield detail

    def action_toggle_expand(self) -> None:
        super().action_toggle_expand()
        self.query_one(".tool-details", Static).display = self._details_visible()

    def _sync_status_classes(self) -> None:
        self.set_class(self.status_state == "running", "-running")
        self.set_class(self.status_state == "waiting", "-waiting")
        self.set_class(self.status_state == "retryable", "-retryable")
        self.set_class(self.status_state == "ok", "-ok")
        self.set_class(self.status_state == "failed", "-failed")

    def _update_visible_output(self) -> None:
        with contextlib.suppress(NoMatches):
            params = self.query_one(".subagent-parameters", Static)
            params.update(_subagent_parameters(self.arguments))
            params.display = self._subagent_parameters_visible()
        output = self.query_one(".tool-output", Static)
        visible_output = _tool_output_visible(self.tool_name, self.output_body)
        output.update(_tool_output_renderable(self.tool_name, self.output_body) if visible_output else "")
        output.display = visible_output

    def _details_visible(self) -> bool:
        return bool(self.details and self.expanded and _is_subagent_tool_name(self.tool_name))

    def _subagent_parameters_visible(self) -> bool:
        return bool(self.arguments and _is_subagent_tool_name(self.tool_name))


class LocalCommandBlock(Vertical, can_focus=True):
    def __init__(self, view: ToolOutputView, *, call_id: str = "") -> None:
        self.display_model = transcript_display("tool")
        super().__init__(classes="transcript-block tool-block local-command-block")
        self.call_id = call_id
        self.view = view
        self.title = _local_command_title(view)
        self.output_body = _local_command_output_body(view)
        self.meta_body = _local_command_meta_body(view)
        self.set_class(view.ok is True, "-ok")
        self.set_class(view.ok is False, "-failed")

    @classmethod
    def from_output(cls, view: ToolOutputView, *, call_id: str = "") -> LocalCommandBlock:
        return cls(view, call_id=call_id)

    def compose(self) -> ComposeResult:
        yield Static(self.output_body, classes="block-body local-command-output")
        meta = Static(self.meta_body, classes="tool-details local-command-meta")
        meta.display = bool(self.meta_body)
        yield meta
