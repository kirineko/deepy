from __future__ import annotations

import asyncio
import contextlib
import os
import select
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import termios
    import tty
except ImportError:  # pragma: no cover - exercised on Windows.
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:  # pragma: no cover - exercised on non-Windows platforms.
    msvcrt = None  # type: ignore[assignment]

from rich.console import Console
from rich.prompt import Prompt
from rich.text import Text

from deepy import __version__
from deepy.config import Settings
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary, run_prompt_once
from deepy.sessions import DeepyJsonlSession, SessionEntry, list_session_entries
from deepy.skills import discover_skills, find_skill, format_skills_for_terminal, read_skill_body
from deepy.status import build_status_report, format_status_report
from deepy.update_check import VersionUpdate
from deepy.update_check import check_for_version_update
from deepy.ui.ask_user_question import OTHER_VALUE
from deepy.ui.ask_user_question import AskUserQuestionItem
from deepy.ui.ask_user_question import AskUserQuestionOptionEntry
from deepy.ui.ask_user_question import build_answer_for_question
from deepy.ui.ask_user_question import build_options
from deepy.ui.ask_user_question import format_ask_user_question_answers
from deepy.ui.ask_user_question import format_ask_user_question_decline
from deepy.ui.ask_user_question import normalize_questions
from deepy.ui.exit_summary import build_exit_summary_text
from deepy.ui.message_view import (
    build_thinking_summary,
    format_tool_call_summary,
    format_tool_progress_summary,
    parse_tool_output,
    render_tool_diff_preview,
)
from deepy.ui.markdown import render_markdown
from deepy.ui.prompt_input import CTRL_D_EXIT_CONFIRM_SIGNAL
from deepy.ui.prompt_input import build_prompt_toolbar, create_prompt_session, prompt_for_input
from deepy.ui.session_list import resolve_session_selection
from deepy.ui.session_picker import ResumeSessionPreview
from deepy.ui.session_picker import format_resume_session_choices
from deepy.ui.session_picker import pick_resume_session
from deepy.ui.slash_commands import build_slash_commands
from deepy.ui.styles import (
    STYLE_ASSISTANT,
    STYLE_ERROR,
    STYLE_INFO,
    STYLE_MUTED,
    STYLE_USER,
    status_style,
)
from deepy.ui.welcome import build_welcome_panel
from deepy.usage import TokenUsage, format_usage_line
from deepy.utils import json as json_utils


RunOnce = Callable[..., Awaitable[RunSummary]]
InputFunc = Callable[[str], str]
VersionUpdateChecker = Callable[[str], VersionUpdate | None]


@dataclass(frozen=True)
class SlashCommand:
    name: str
    argument: str = ""


@dataclass(frozen=True)
class ToolCallDisplay:
    summary: str
    name: str


def parse_slash_command(text: str) -> SlashCommand | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    command, _, argument = stripped[1:].partition(" ")
    return SlashCommand(name=command, argument=argument.strip())


def run_interactive(
    settings: Settings,
    *,
    project_root: Path | None = None,
    console: Console | None = None,
    run_once: RunOnce = run_prompt_once,
    version_update_checker: VersionUpdateChecker | None = check_for_version_update,
) -> int:
    root = (project_root or Path.cwd()).resolve()
    output = console or Console()
    session_id: str | None = None
    version_update = _check_startup_version_update(version_update_checker)

    loaded_skill_names: list[str] = []
    ctrl_d_exit_pending = False
    context_status = _format_context_footer(
        session_id,
        project_root=root,
        settings=settings,
    )
    prompt_session = create_prompt_session(
        slash_commands=build_slash_commands(discover_skills(root)),
    )
    output.print(
        build_welcome_panel(
            model=settings.model.name,
            thinking_enabled=settings.model.thinking_enabled,
            reasoning_effort=settings.model.reasoning_effort,
            project_root=root,
            skills=discover_skills(root),
            current_version=__version__,
            version_update=version_update,
        )
    )

    while True:
        try:
            text = prompt_for_input(
                prompt_session,
                bottom_toolbar=build_prompt_toolbar(context_status),
            )
        except EOFError:
            if ctrl_d_exit_pending:
                output.print()
                return 0
            ctrl_d_exit_pending = True
            output.print(f"[{STYLE_MUTED}]Press Ctrl+D again to exit.[/]")
            continue
        except KeyboardInterrupt:
            output.print()
            return 0

        if text == CTRL_D_EXIT_CONFIRM_SIGNAL:
            if ctrl_d_exit_pending:
                output.print()
                return 0
            ctrl_d_exit_pending = True
            output.print(f"[{STYLE_MUTED}]Press Ctrl+D again to exit.[/]")
            continue

        ctrl_d_exit_pending = False
        if not text:
            continue

        slash = parse_slash_command(text)
        if slash is not None:
            next_session = _handle_slash_command(
                slash,
                output,
                root,
                session_id,
                loaded_skill_names,
                settings=settings,
            )
            if next_session == "__exit__":
                return 0
            session_id = next_session
            if slash.name in {"new", "resume"}:
                context_status = _format_context_footer(
                    session_id,
                    project_root=root,
                    settings=settings,
                )
            continue

        _print_user_input(output, text)
        summary = _run_once_with_status(
            output,
            run_once,
            text,
            project_root=root,
            settings=settings,
            session_id=session_id,
            skill_names=list(loaded_skill_names),
        )
        session_id = summary.session_id
        if summary.status == "waiting_for_user":
            response = _collect_pending_question_response(output, summary.pending_questions)
            if response:
                _print_user_input(output, response)
                summary = _run_once_with_status(
                    output,
                    run_once,
                    response,
                    project_root=root,
                    settings=settings,
                    session_id=session_id,
                    skill_names=list(loaded_skill_names),
                )
                session_id = summary.session_id
        _print_assistant_output(output, summary.output)
        _print_usage_footer(output, summary, settings=settings, project_root=root)
        context_status = _format_context_footer(
            summary.session_id,
            project_root=root,
            settings=settings,
        )


def _check_startup_version_update(
    version_update_checker: VersionUpdateChecker | None,
) -> VersionUpdate | None:
    if version_update_checker is None:
        return None
    try:
        return version_update_checker(__version__)
    except Exception:
        return None


def _run_once_with_status(
    console: Console,
    run_once: RunOnce,
    prompt: str,
    **kwargs: object,
) -> RunSummary:
    original_emit_event = kwargs.pop("emit_event", None)
    original_should_interrupt = kwargs.pop("should_interrupt", None)
    project_root = kwargs.get("project_root")
    project_root_text = str(project_root) if project_root is not None else None
    renderer: TerminalStreamRenderer | None = None
    started_at = time.monotonic()
    interrupt_requested = threading.Event()

    def should_interrupt() -> bool:
        if interrupt_requested.is_set():
            return True
        return bool(callable(original_should_interrupt) and original_should_interrupt())

    kwargs["should_interrupt"] = should_interrupt

    with console.status(_working_status_text(started_at), spinner="dots") as status:
        renderer = TerminalStreamRenderer(
            console,
            project_root=project_root_text,
            status=status,
            status_started_at=started_at,
        )
        stop_status_refresh = threading.Event()
        status_thread = threading.Thread(
            target=_refresh_working_status,
            args=(renderer, stop_status_refresh),
            daemon=True,
        )
        status_thread.start()

        try:
            with _esc_interrupt_watcher(interrupt_requested):
                def emit_event(event: DeepyStreamEvent) -> None:
                    renderer(event)
                    if callable(original_emit_event):
                        original_emit_event(event)

                summary = asyncio.run(run_once(prompt, **kwargs, emit_event=emit_event))
        finally:
            stop_status_refresh.set()
            status_thread.join(timeout=0.2)

    renderer.flush()
    return summary


@contextlib.contextmanager
def _esc_interrupt_watcher(interrupt_requested: threading.Event):
    if termios is not None and tty is not None and Path("/dev/tty").exists():
        target = _watch_posix_esc_keypress
    elif msvcrt is not None:
        target = _watch_windows_esc_keypress
    else:
        yield
        return

    stop_event = threading.Event()
    thread = threading.Thread(
        target=target,
        args=(interrupt_requested, stop_event),
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=0.2)


def _watch_posix_esc_keypress(
    interrupt_requested: threading.Event,
    stop_event: threading.Event,
) -> None:
    fd: int | None = None
    old_attrs: list[Any] | None = None
    try:
        if termios is None or tty is None:
            return
        fd = os.open("/dev/tty", os.O_RDONLY | os.O_NONBLOCK)
        old_attrs = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        while not stop_event.is_set() and not interrupt_requested.is_set():
            readable, _, _ = select.select([fd], [], [], 0.05)
            if not readable:
                continue
            try:
                data = os.read(fd, 32)
            except BlockingIOError:
                continue
            if b"\x1b" in data:
                interrupt_requested.set()
                return
    except Exception:
        return
    finally:
        if fd is not None:
            if old_attrs is not None:
                with contextlib.suppress(Exception):
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            with contextlib.suppress(Exception):
                os.close(fd)


def _watch_windows_esc_keypress(
    interrupt_requested: threading.Event,
    stop_event: threading.Event,
) -> None:
    if msvcrt is None:
        return
    while not stop_event.is_set() and not interrupt_requested.is_set():
        try:
            if not msvcrt.kbhit():
                time.sleep(0.05)
                continue
            key = msvcrt.getwch()
        except Exception:
            return
        if key == "\x1b":
            interrupt_requested.set()
            return


class TerminalStreamRenderer:
    def __init__(
        self,
        console: Console,
        *,
        project_root: str | None = None,
        status: Any | None = None,
        status_started_at: float | None = None,
    ) -> None:
        self.console = console
        self.project_root = project_root
        self.status = status
        self.status_started_at = (
            status_started_at if status_started_at is not None else time.monotonic()
        )
        self.status_detail = ""
        self.pending_tool_calls: dict[str, ToolCallDisplay] = {}
        self.reasoning_text = ""
        self.reasoning_flushed = False

    def __call__(self, event: DeepyStreamEvent) -> None:
        _print_stream_event(
            self.console,
            event,
            project_root=self.project_root,
            pending_tool_calls=self.pending_tool_calls,
            reasoning_sink=self,
        )

    def add_reasoning(self, text: str) -> None:
        if self.reasoning_flushed:
            self.reasoning_text = ""
            self.reasoning_flushed = False
        self.reasoning_text += text
        summary = build_thinking_summary(self.reasoning_text)
        if self.status is not None and summary:
            self.update_status(f"Thinking {summary}")

    def set_tool_status(self, summary: str) -> None:
        if self.status is not None and summary:
            self.update_status(f"Running {summary}")

    def update_status(self, detail: str | None = None) -> None:
        if detail is not None:
            self.status_detail = detail
        if self.status is not None:
            self.status.update(_working_status_text(self.status_started_at, self.status_detail))

    def flush(self) -> None:
        if self.reasoning_flushed:
            return
        summary = build_thinking_summary(self.reasoning_text)
        if not summary:
            return
        self.console.print(
            Text.assemble(
                ("• ", STYLE_MUTED),
                ("Thinking  ", f"bold {STYLE_MUTED}"),
                (summary, STYLE_MUTED),
            )
        )
        self.reasoning_flushed = True


def _handle_slash_command(
    command: SlashCommand,
    console: Console,
    project_root: Path,
    current_session_id: str | None,
    loaded_skill_names: list[str] | None = None,
    settings: Settings | None = None,
    input_func: InputFunc | None = None,
) -> str | None:
    loaded_skill_names = loaded_skill_names if loaded_skill_names is not None else []
    settings = settings or Settings()
    if command.name in {"exit", "quit"}:
        _print_exit_summary(console, project_root, current_session_id, settings)
        return "__exit__"
    if command.name == "help":
        console.print("/help       Show commands")
        console.print("/skills     List available skills")
        console.print("/skill NAME Show a skill document")
        console.print("/use NAME   Load a skill for subsequent prompts")
        console.print("/status     Show project status")
        console.print("/sessions   List project sessions")
        console.print("/resume ID  Resume a session")
        console.print("/new        Start a new session")
        console.print("/exit       Quit")
        return current_session_id
    if command.name == "new":
        loaded_skill_names.clear()
        console.print("Started a new session.")
        return None
    if command.name == "resume":
        entries = list_session_entries(project_root)
        previews = _build_resume_session_previews(project_root, entries)
        if command.argument:
            selected = resolve_session_selection(entries, command.argument)
            session_id = selected.id if selected is not None else command.argument
            _resume_session(console, project_root, session_id)
            return session_id
        if not entries:
            console.print("No sessions found.")
            return current_session_id
        invalid_selection = False
        if input_func is not None:
            console.print(format_resume_session_choices(previews))
            selection = input_func("Resume session number or id")
            selected = resolve_session_selection(entries, selection)
            session_id = selected.id if selected is not None else ""
            invalid_selection = bool(selection.strip()) and selected is None
        else:
            session_id = pick_resume_session(previews) or ""
            selected = resolve_session_selection(entries, session_id) if session_id else None
            invalid_selection = bool(session_id) and selected is None
        if selected is None:
            message = "Invalid session selection." if invalid_selection else "Resume canceled."
            style = STYLE_ERROR if invalid_selection else STYLE_MUTED
            console.print(f"[{style}]{message}[/]")
            return current_session_id
        _resume_session(console, project_root, selected.id)
        return selected.id
    if command.name == "sessions":
        entries = list_session_entries(project_root)
        if not entries:
            console.print("No sessions found.")
            return current_session_id
        for entry in entries:
            console.print(
                f"{entry.id}\tupdated={entry.updated_at}\thistory_tokens={entry.active_tokens}\t"
                f"{format_usage_line(entry.usage)}"
            )
        return current_session_id
    if command.name == "status":
        console.print(format_status_report(build_status_report(project_root, settings)))
        return current_session_id
    if command.name == "skills":
        console.print(format_skills_for_terminal(discover_skills(project_root)))
        return current_session_id
    if command.name == "skill":
        if not command.argument:
            console.print(f"[{STYLE_ERROR}]Usage:[/] /skill NAME")
            return current_session_id
        skill = find_skill(project_root, command.argument)
        if skill is None:
            console.print(f"[{STYLE_ERROR}]Skill not found:[/] {command.argument}")
            return current_session_id
        console.print(read_skill_body(skill) or "(empty skill)")
        return current_session_id
    if command.name == "use":
        if not command.argument:
            console.print(f"[{STYLE_ERROR}]Usage:[/] /use NAME")
            return current_session_id
        skill = find_skill(project_root, command.argument)
        if skill is None:
            console.print(f"[{STYLE_ERROR}]Skill not found:[/] {command.argument}")
            return current_session_id
        if skill.name not in loaded_skill_names:
            loaded_skill_names.append(skill.name)
        console.print(f"Loaded skill: {skill.name}")
        return current_session_id

    console.print(f"[{STYLE_ERROR}]Unknown command:[/] /{command.name}")
    return current_session_id


def _resume_session(console: Console, project_root: Path, session_id: str) -> None:
    console.print(Text.assemble(("Resuming session ", STYLE_MUTED), (session_id, STYLE_INFO)))
    _print_session_history(console, project_root, session_id)


def _build_resume_session_previews(
    project_root: Path,
    entries: list[SessionEntry],
) -> list[ResumeSessionPreview]:
    previews: list[ResumeSessionPreview] = []
    for entry in entries:
        items = _load_session_items(project_root, entry.id)
        previews.append(
            ResumeSessionPreview(
                id=entry.id,
                title=_session_title(items),
                status=_session_status(items),
                updated_at=entry.updated_at,
                active_tokens=entry.active_tokens,
            )
        )
    return previews


def _print_session_history(console: Console, project_root: Path, session_id: str) -> None:
    items = _load_session_items(project_root, session_id)
    if not items:
        console.print(f"[{STYLE_MUTED}]No visible history for this session.[/]")
        return

    console.print(Text("History", style=f"bold {STYLE_MUTED}"))
    renderer = TerminalStreamRenderer(console, project_root=str(project_root))
    for item in items:
        _print_history_item(console, item, renderer)
    renderer.flush()


def _print_history_item(
    console: Console,
    item: dict[str, Any],
    renderer: TerminalStreamRenderer,
) -> None:
    item_type = _item_type(item)
    role = _role(item)

    if item_type == "reasoning":
        renderer(DeepyStreamEvent(kind="reasoning_delta", text=_reasoning_text(item)))
        return

    if item_type == "function_call":
        renderer(_history_tool_call_event(item))
        return

    if item_type == "function_call_output":
        renderer(_history_tool_output_event(item))
        return

    if role == "tool":
        renderer(_history_tool_output_event(item))
        return

    if role == "user":
        renderer.flush()
        _print_user_input(console, _item_text(item))
        return

    if role == "assistant":
        text = _item_text(item)
        tool_calls = _chat_tool_calls(item)
        if text.strip():
            renderer.flush()
            _print_assistant_output(console, text)
        for tool_call in tool_calls:
            renderer(_history_tool_call_event(tool_call))
        return


def _history_tool_call_event(item: dict[str, Any]) -> DeepyStreamEvent:
    return DeepyStreamEvent(
        kind="tool_call",
        name=_tool_call_name(item),
        payload={
            "call_id": _call_id(item),
            "arguments": _tool_call_arguments(item),
        },
    )


def _history_tool_output_event(item: dict[str, Any]) -> DeepyStreamEvent:
    return DeepyStreamEvent(
        kind="tool_output",
        payload={"call_id": _call_id(item)},
        text=_tool_output_text(item),
    )


def _load_session_items(project_root: Path, session_id: str) -> list[dict[str, Any]]:
    try:
        return asyncio.run(DeepyJsonlSession.open(project_root, session_id).get_items())
    except Exception:
        return []


def _session_title(items: list[dict[str, Any]]) -> str:
    for item in items:
        if _role(item) == "user":
            text = _item_text(item)
            if text.strip():
                return text
    for item in items:
        text = _item_text(item)
        if text.strip():
            return text
    return "Untitled"


def _session_status(items: list[dict[str, Any]]) -> str:
    if not items:
        return "empty"
    for item in reversed(items):
        if _role(item) == "user":
            break
        if _is_waiting_tool_output(item):
            return "waiting"
    last = items[-1]
    if _item_type(last) == "function_call":
        return "interrupted"
    if _is_failed_tool_output(last):
        return "failed"
    return "completed"


def _is_waiting_tool_output(item: dict[str, Any]) -> bool:
    if _item_type(item) != "function_call_output" and _role(item) != "tool":
        return False
    return parse_tool_output(_tool_output_text(item)).await_user_response


def _is_failed_tool_output(item: dict[str, Any]) -> bool:
    if _item_type(item) != "function_call_output" and _role(item) != "tool":
        return False
    return parse_tool_output(_tool_output_text(item)).ok is False


def _item_text(item: dict[str, Any]) -> str:
    if "content" in item:
        return _content_text(item["content"])
    if "text" in item:
        return _content_text(item["text"])
    if "output" in item:
        return _content_text(item["output"])
    return ""


def _reasoning_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("content", "summary", "text"):
        if key in item:
            text = _content_text(item[key])
            if text.strip():
                parts.append(text)
    return "\n".join(parts)


def _tool_output_text(item: dict[str, Any]) -> str:
    if "output" in item:
        return _content_text(item["output"])
    return _item_text(item)


def _content_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for part in value:
            text = _content_text_part(part)
            if text:
                parts.append(text)
        return "\n".join(parts)
    if value is None:
        return ""
    if isinstance(value, dict):
        text = _content_text_part(value)
        return text or json_utils.dumps(value)
    return str(value)


def _content_text_part(part: object) -> str:
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return ""
    for key in ("text", "input_text", "output_text", "refusal"):
        value = part.get(key)
        if isinstance(value, str):
            return value
    return ""


def _chat_tool_calls(item: dict[str, Any]) -> list[dict[str, Any]]:
    value = item.get("tool_calls")
    if not isinstance(value, list):
        return []
    return [tool_call for tool_call in value if isinstance(tool_call, dict)]


def _tool_call_name(item: dict[str, Any]) -> str:
    name = item.get("name")
    if isinstance(name, str) and name:
        return name
    function = item.get("function")
    if isinstance(function, dict):
        function_name = function.get("name")
        if isinstance(function_name, str) and function_name:
            return function_name
    return "tool"


def _tool_call_arguments(item: dict[str, Any]) -> str:
    arguments = item.get("arguments")
    if isinstance(arguments, str):
        return arguments
    if arguments is not None:
        return json_utils.dumps(arguments)
    function = item.get("function")
    if isinstance(function, dict):
        function_arguments = function.get("arguments")
        if isinstance(function_arguments, str):
            return function_arguments
        if function_arguments is not None:
            return json_utils.dumps(function_arguments)
    return ""


def _item_type(item: dict[str, Any]) -> str:
    value = item.get("type")
    return value if isinstance(value, str) else ""


def _role(item: dict[str, Any]) -> str:
    value = item.get("role")
    return value if isinstance(value, str) else ""


def _call_id(item: dict[str, Any]) -> str:
    for key in ("call_id", "tool_call_id", "id"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    return ""


def _print_exit_summary(
    console: Console,
    project_root: Path,
    session_id: str | None,
    settings: Settings,
) -> None:
    session_entry: SessionEntry | None = None
    messages: list[dict[str, object]] = []
    if session_id:
        session_entry = next(
            (entry for entry in list_session_entries(project_root) if entry.id == session_id),
            None,
        )
        try:
            messages = asyncio.run(DeepyJsonlSession.open(project_root, session_id).get_items())
        except Exception:
            messages = []
    console.print(
        build_exit_summary_text(
            session=session_entry,
            messages=messages,
            model=settings.model.name,
        )
    )


def _print_usage_footer(
    console: Console,
    summary: RunSummary,
    *,
    settings: Settings | None = None,
    project_root: Path | None = None,
) -> None:
    if summary.usage.known:
        duration = _format_duration_ms(summary.duration_ms) if summary.duration_ms > 0 else ""
        prefix = f"time {duration} · " if duration else ""
        console.print(
            f"[{STYLE_MUTED}]turn API usage[/] {prefix}{_format_turn_usage_line(summary.usage)}"
        )
    elif summary.duration_ms > 0:
        console.print(f"[{STYLE_MUTED}]turn time[/] {_format_duration_ms(summary.duration_ms)}")


def _format_context_footer(
    session_id: str | None,
    *,
    project_root: Path | None = None,
    settings: Settings | None = None,
) -> str:
    if settings is None:
        return ""

    window_tokens = settings.context.window_tokens
    compact_threshold = settings.context.resolved_compact_threshold
    if window_tokens <= 0:
        return ""

    used_tokens = _session_active_tokens(project_root, session_id)
    used_text = f"{used_tokens:,}" if used_tokens is not None else "unknown"
    used_ratio = (
        f" ({used_tokens / window_tokens * 100:.1f}%)"
        if used_tokens is not None
        else ""
    )
    if compact_threshold > 0:
        compact_progress = (
            f" ({used_tokens / compact_threshold * 100:.1f}%)"
            if used_tokens is not None
            else ""
        )
        parts = [f"context used {used_text} / {compact_threshold:,} to compact{compact_progress}"]
        parts.append(f"window {window_tokens:,}")
        if used_tokens is not None and used_tokens >= compact_threshold:
            parts.append("compact next request")
    else:
        parts = [f"context used {used_text} / {window_tokens:,}{used_ratio}"]

    return " · ".join(parts)


def _session_active_tokens(project_root: Path | None, session_id: str | None) -> int | None:
    if not session_id:
        return 0
    if project_root is None:
        return None
    try:
        entries = list_session_entries(project_root)
    except Exception:
        return None
    entry = next((item for item in entries if item.id == session_id), None)
    return entry.active_tokens if entry is not None else None


def _format_turn_usage_line(usage: TokenUsage) -> str:
    prefix = f"requests {usage.requests:,} · " if usage.requests > 0 else ""
    return f"{prefix}{format_usage_line(usage)}"


def _refresh_working_status(
    renderer: TerminalStreamRenderer,
    stop_event: threading.Event,
) -> None:
    while not stop_event.wait(1):
        renderer.update_status()


def _working_status_text(started_at: float, detail: str = "") -> Text:
    elapsed = _format_duration_ms(int((time.monotonic() - started_at) * 1000)) or "0s"
    text = Text.assemble(
        ("Working ", f"bold {STYLE_MUTED}"),
        (f"({elapsed} · esc to interrupt)", STYLE_MUTED),
    )
    if detail:
        text.append(" · ", style=STYLE_MUTED)
        text.append(detail, style=STYLE_MUTED)
    return text


def _format_duration_ms(duration_ms: int) -> str:
    seconds = max(0, int(duration_ms // 1000))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def _print_user_input(console: Console, text: str) -> None:
    if not text.strip():
        return
    lines = text.rstrip().splitlines() or [text.rstrip()]
    rendered = Text()
    for index, line in enumerate(lines):
        if index:
            rendered.append("\n")
            rendered.append("  ", style=STYLE_USER)
        else:
            rendered.append("> ", style=STYLE_USER)
        rendered.append(line, style=STYLE_USER)
    console.print(rendered)


def _print_assistant_output(console: Console, text: str) -> None:
    if not text.strip():
        return
    console.print()
    console.print(f"[bold {STYLE_ASSISTANT}]Deepy[/]")
    console.print(render_markdown(text.rstrip()))


def _print_stream_event(
    console: Console,
    event: DeepyStreamEvent,
    *,
    project_root: str | None = None,
    pending_tool_calls: dict[str, ToolCallDisplay] | None = None,
    reasoning_sink: TerminalStreamRenderer | None = None,
) -> None:
    if event.kind in {"text_delta", "message"}:
        return
    if event.kind == "reasoning_delta":
        if reasoning_sink is not None:
            reasoning_sink.add_reasoning(event.text)
        return
    if event.kind == "tool_call":
        summary = format_tool_call_summary(
            event.name or "tool",
            _string_payload(event.payload.get("arguments")),
            project_root=project_root,
        )
        if pending_tool_calls is not None:
            call_id = _string_payload(event.payload.get("call_id"))
            if call_id:
                pending_tool_calls[call_id] = ToolCallDisplay(
                    summary=summary,
                    name=event.name or "tool",
                )
                if reasoning_sink is not None:
                    reasoning_sink.set_tool_status(summary)
                return
        console.print(_status_line(summary, STYLE_INFO))
        return
    if event.kind == "tool_output":
        if reasoning_sink is not None:
            reasoning_sink.flush()
        view = parse_tool_output(event.text)
        call_id = _string_payload(event.payload.get("call_id"))
        call = pending_tool_calls.pop(call_id, None) if pending_tool_calls is not None else None
        call_summary = call.summary if call is not None else view.name
        summary = format_tool_progress_summary(call_summary, event.text)
        console.print(_status_line(summary, status_style(view.ok)))
        diff = render_tool_diff_preview(event.text)
        if diff:
            console.print(diff)
        return
    if event.kind == "agent_updated":
        return
    if event.kind == "usage":
        return


def _string_payload(value: object) -> str:
    return value if isinstance(value, str) else ""


def _status_line(text: str, style: str) -> Text:
    return Text.assemble(("• ", style), (text, f"bold {style}"))


def _collect_pending_question_response(
    console: Console,
    pending_questions: list[dict[str, object]],
    input_func: InputFunc | None = None,
) -> str:
    questions = normalize_questions(pending_questions)
    if not questions:
        return ""
    answers: dict[str, str] = {}
    chooser = input_func or (lambda prompt: Prompt.ask(prompt, default=""))
    for question in questions:
        answer = _prompt_for_question(console, question, chooser)
        if answer is None:
            return format_ask_user_question_decline()
        answers[question.question] = answer
    return format_ask_user_question_answers(answers)


def _prompt_for_question(
    console: Console,
    question: AskUserQuestionItem,
    input_func: InputFunc,
) -> str | None:
    options = build_options(question)
    console.print(f"\n[bold]Question:[/bold] {question.question}")
    for index, option in enumerate(options, 1):
        detail = f" - {option.description}" if option.description else ""
        console.print(f"{index}. {option.label}{detail}")
    raw_answer = input_func("Answer number, text, or empty to decline").strip()
    if not raw_answer:
        return None
    return _answer_question_from_text(question, raw_answer)


def _answer_question_from_text(question: AskUserQuestionItem, raw_answer: str) -> str | None:
    options = build_options(question)
    if question.multi_select:
        selected_values: list[str] = []
        custom_values: list[str] = []
        for token in [part.strip() for part in raw_answer.split(",") if part.strip()]:
            option = _option_from_token(options, token)
            if option is not None:
                selected_values.append(option.value)
            else:
                custom_values.append(token)
        if custom_values:
            selected_values.append(OTHER_VALUE)
        return build_answer_for_question(
            question,
            None,
            selected_values,
            ", ".join(custom_values),
        )

    option = _option_from_token(options, raw_answer)
    if option is None:
        option = next((item for item in options if item.value == OTHER_VALUE), None)
    other_text = raw_answer if option is not None and option.is_other else ""
    return build_answer_for_question(question, option, [], other_text)


def _option_from_token(
    options: list[AskUserQuestionOptionEntry],
    token: str,
) -> AskUserQuestionOptionEntry | None:
    if token.isdigit():
        index = int(token) - 1
        if 0 <= index < len(options):
            return options[index]
    lowered = token.casefold()
    return next((option for option in options if option.label.casefold() == lowered), None)
