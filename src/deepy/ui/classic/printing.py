from __future__ import annotations

import os
import re
import shutil
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from deepy.llm.events import DeepyStreamEvent
from deepy.ui.classic.terminal_patchable import resolve as _resolve
from deepy.ui.classic.runtime_workers import ToolCallDisplay
from deepy.ui.classic.status.runtime_status import _phase_status_text
from deepy.ui.classic.status_display import _phase_status_display
from deepy.ui.shared.render.message_view import (
    ToolOutputView,
    format_tool_display_label,
    format_tool_call_summary,
    format_tool_progress_summary,
    parse_tool_output,
    render_shell_output_block,
    render_todo_board,
    should_omit_success_summary,
    tool_status_style,
)
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette
from deepy.utils import json as json_utils
from deepy.ui.classic.prompt.prompt_input import measure_text_rows

if TYPE_CHECKING:
    from deepy.ui.classic.stream_render import TerminalStreamRenderer


def _print_submitted_user_input(console: Console, text: str, *, palette: UiPalette | None = None) -> None:
    _clear_submitted_prompt_echo(console, text)
    _print_user_input(console, text, palette=palette)


def _clear_submitted_prompt_echo(console: Console, text: str) -> None:
    if not text.strip():
        return
    file = getattr(console, "file", None)
    if file is None:
        return
    isatty = getattr(file, "isatty", None)
    if not callable(isatty) or not isatty():
        return

    rows = _submitted_prompt_echo_rows(text, _terminal_columns(console))
    for _ in range(rows):
        file.write("\x1b[1A\x1b[2K")
    file.write("\r")
    file.flush()


def _terminal_columns(console: Console) -> int:
    fallback = (max(1, console.width), 24)
    return max(1, shutil.get_terminal_size(fallback).columns)


def _submitted_prompt_echo_rows(text: str, columns: int) -> int:
    lines = text.rstrip("\n").split("\n") or [""]
    return sum(
        measure_text_rows(line, width=columns, initial_column=2 if index == 0 else 0)
        for index, line in enumerate(lines)
    )


def _print_user_input(console: Console, text: str, *, palette: UiPalette | None = None) -> None:
    palette = palette or DARK_PALETTE
    if not text.strip():
        return
    lines = text.rstrip().splitlines() or [text.rstrip()]
    rendered = Text()
    for index, line in enumerate(lines):
        if index:
            rendered.append("\n")
            rendered.append("  ", style=palette.user)
        else:
            rendered.append("> ", style=palette.user)
        rendered.append(line, style=palette.user)
    console.print(rendered)


def _print_assistant_output(
    console: Console,
    text: str,
    *,
    palette: UiPalette | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    if not text.strip():
        return
    with _phase_status_display(
        console,
        _phase_status_text("rendering response", palette),
        palette=palette,
    ):
        rendered = _resolve("render_markdown")(text.rstrip(), palette=palette, width=console.width)
    console.print()
    console.print(_status_line("[Assistant]", palette.assistant))
    console.print(rendered)


def _print_stream_event(
    console: Console,
    event: DeepyStreamEvent,
    *,
    project_root: str | None = None,
    pending_tool_calls: dict[str, ToolCallDisplay] | None = None,
    reasoning_sink: TerminalStreamRenderer | None = None,
    palette: UiPalette | None = None,
    approved_preflight_diffs: set[str] | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    if event.kind in {"text_delta", "message"}:
        return
    if event.kind == "reasoning_delta":
        if reasoning_sink is not None:
            reasoning_sink.add_reasoning(event.text)
        return
    if event.kind == "tool_call":
        if reasoning_sink is not None:
            reasoning_sink.flush()
        tool_name = event.name or "tool"
        arguments = _string_payload(event.payload.get("arguments"))
        call_id = ""
        is_subagent = tool_name.startswith("subagent_")
        summary = (
            format_tool_display_label(tool_name)
            if is_subagent
            else format_tool_call_summary(
                tool_name,
                arguments,
                project_root=project_root,
            )
        )
        if pending_tool_calls is not None:
            call_id = _string_payload(event.payload.get("call_id"))
            if call_id:
                pending_tool_calls[call_id] = ToolCallDisplay(
                    summary=summary,
                    name=tool_name,
                )
        if is_subagent:
            console.print(_status_line(f"{summary} started", palette.info))
            task = _subagent_input_markdown(arguments)
            if task:
                console.print(_subagent_input_panel(task, palette=palette, width=console.width))
        if reasoning_sink is not None:
            reasoning_sink.set_tool_status(tool_name)
        return
    if event.kind == "tool_output":
        if reasoning_sink is not None:
            reasoning_sink.flush()
        view = parse_tool_output(event.text)
        call_id = _string_payload(event.payload.get("call_id"))
        call = pending_tool_calls.pop(call_id, None) if pending_tool_calls is not None else None
        call_summary = call.summary if call is not None else ""
        summary = (
            _audit_rejection_tool_summary(call.name if call is not None else view.name)
            if _is_audit_rejection_tool_output(event.text, view)
            else format_tool_progress_summary(call_summary, event.text)
        )
        diff_text = _tool_output_diff_text(event.text)
        suppress_preflight_diff = (
            diff_text is not None
            and approved_preflight_diffs is not None
            and diff_text in approved_preflight_diffs
        )
        diff = None if suppress_preflight_diff else _resolve("render_tool_diff_preview")(
            event.text,
            palette=palette,
            width=console.width,
            project_root=project_root,
        )
        if suppress_preflight_diff and diff_text is not None and approved_preflight_diffs is not None:
            approved_preflight_diffs.discard(diff_text)
        if not should_omit_success_summary(view, diff):
            console.print(_status_line(summary, tool_status_style(view, palette)))
        if _should_print_tool_output_debug(view):
            console.print(Text("Tool output JSON:", style=palette.muted))
            console.print(Text(_format_tool_output_debug(event.text), style=palette.muted))
        shell_output = render_shell_output_block(event.text, palette=palette, width=console.width)
        if shell_output:
            console.print(shell_output)
        todo_board = render_todo_board(event.text, palette=palette, width=console.width)
        if todo_board:
            console.print(todo_board)
        if diff:
            console.print(diff)
        return
    if event.kind == "agent_updated":
        return
    if event.kind == "usage":
        return
    if event.kind == "status":
        console.print(_status_line(event.text, palette.info))
        return


def _stream_event_writes_terminal(event: DeepyStreamEvent) -> bool:
    if event.kind == "reasoning_delta":
        return bool(event.text)
    if event.kind == "tool_call":
        return bool((event.name or "").startswith("subagent_"))
    return event.kind in {"tool_output", "status"}


def _tool_output_diff_text(output: str) -> str | None:
    view = parse_tool_output(output)
    if view.ok is not True:
        return None
    return view.diff_preview or view.diff


def _is_audit_rejection_tool_output(output: str, view: ToolOutputView) -> bool:
    if view.ok is True:
        return False
    normalized = output.strip().lower()
    return "audit approval" in normalized and "reject" in normalized


def _audit_rejection_tool_summary(tool_name: str) -> str:
    return f"{format_tool_display_label(tool_name or 'tool')} rejected"


def _silent_generation_status_detail(event: DeepyStreamEvent) -> str | None:
    if event.kind in {"text_delta", "message"} and event.text:
        return ""
    if event.kind == "raw_response" and event.text:
        return ""
    return None


def _string_payload(value: object) -> str:
    return value if isinstance(value, str) else ""


def _subagent_input_markdown(arguments: str) -> str:
    if not arguments.strip():
        return ""
    try:
        parsed = json_utils.loads(arguments)
    except json_utils.JSONDecodeError:
        return arguments.strip()
    if not isinstance(parsed, dict):
        return arguments.strip()
    for key in ("input", "task", "prompt", "request"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in parsed.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _subagent_input_panel(
    text: str,
    *,
    palette: UiPalette,
    width: int,
) -> Panel:
    return Panel(
        _resolve("render_markdown")(text, palette=palette, width=max(24, width - 6)),
        title="Subagent Parameters",
        border_style=palette.info,
        padding=(0, 1),
        expand=False,
    )


def _should_print_tool_output_debug(view: object) -> bool:
    return os.environ.get("DEEPY_DEBUG_TOOL_OUTPUT", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
        "all",
    }


def _format_tool_output_debug(output: str) -> str:
    try:
        parsed = json_utils.loads(output)
    except json_utils.JSONDecodeError:
        return output
    return json_utils.dumps_pretty(parsed)


def _status_line(text: str, style: str) -> Text:
    label_match = re.match(r"(\[[^\]]+\])(\s?.*)", text, flags=re.DOTALL)
    if label_match:
        label, detail = label_match.groups()
        return Text.assemble(
            ("• ", style),
            (label, f"bold underline {style}"),
            (detail, style),
        )
    return Text.assemble(("• ", style), (text, style))

