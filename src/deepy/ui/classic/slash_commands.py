from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.text import Text

from deepy.background_tasks import BackgroundTaskManager
from deepy.config import Settings
from deepy.llm.compaction import ContextCompactionError
from deepy.llm.events import DeepyStreamEvent
from deepy.mcp import format_mcp_status
from deepy.session_cost import supports_session_cost
from deepy.sessions import DeepySession, SessionEntry
from deepy.sessions.manager import DeepySessionManager
from deepy.skills import find_skill
from deepy.status import BalanceStatus, build_status_report,  format_compact_status_report
from deepy.ui.classic.commands.config_commands import (
    _handle_input_suggestion_command,
    _handle_theme_command,
    _handle_ui_command,
    _handle_view_command,
)
from deepy.ui.classic.commands.config_setup import _handle_reset_command
from deepy.ui.classic.commands.model_commands import _handle_model_command
from deepy.ui.classic.commands.skill_commands import _handle_skills_command
from deepy.ui.classic.exit_summary import _print_exit_summary
from deepy.ui.classic.footer import _format_session_cache_for_list
from deepy.ui.classic.printing import _print_assistant_output, _print_user_input
from deepy.ui.classic.runtime_workers import _StartupState
from deepy.ui.classic.status.background_tasks import (
    _format_background_tasks_for_terminal,
    _stop_background_tasks_for_terminal,
)
from deepy.ui.classic.status.transcript_parse import (
    _chat_tool_calls,
    _item_text,
    _reasoning_text,
    _tool_output_text,
)
from deepy.ui.classic.stream_render import TerminalStreamRenderer
from deepy.mcp import DeepyMcpRuntime
from deepy.ui.classic.terminal_patchable import resolve as _resolve
from deepy.ui.classic.terminal_types import InputFunc
from deepy.ui.shared.input.commands import SlashCommand
from deepy.ui.shared.render.styles import DARK_PALETTE, UiPalette, resolve_ui_palette
from deepy.ui.shared.session.session_list import resolve_session_selection
from deepy.ui.shared.session.session_picker import ResumeSessionPreview, format_resume_session_choices, pick_resume_session
from deepy.ui.shared.session.session_transcript import (
    history_tool_call_event as _history_tool_call_event,
    history_tool_output_event,
    item_type as _item_type,
    role as _role,
    session_status,
    session_title,
)
from deepy.usage import format_usage_line


def _handle_slash_command(
    command: SlashCommand,
    console: Console,
    project_root: Path,
    current_session_id: str | None,
    loaded_skill_names: list[str] | None = None,
    settings: Settings | None = None,
    input_func: InputFunc | None = None,
    palette: UiPalette | None = None,
    mcp_runtime: DeepyMcpRuntime | None = None,
    background_tasks: BackgroundTaskManager | None = None,
    startup_state: _StartupState | None = None,
) -> str | None:
    loaded_skill_names = loaded_skill_names if loaded_skill_names is not None else []
    settings = settings or Settings()
    palette = palette or resolve_ui_palette(settings.ui.theme)
    if command.name in {"exit", "quit"}:
        _print_exit_summary(console, project_root, current_session_id, settings)
        return "__exit__"
    if command.name == "help":
        console.print("/help       Show commands")
        console.print("/skills     Manage skills")
        console.print("/skills show NAME")
        console.print("/skills use NAME")
        console.print("/explore    Delegate investigation to the explore subagent")
        console.print("/reviewer   Delegate review to the reviewer subagent")
        console.print("/tester     Delegate verification to the tester subagent")
        console.print("/NAME       Invoke a skill by name")
        console.print("/init      Create or update project AGENTS.md")
        console.print("/mcp       Show MCP server status and tools")
        console.print("/ps        Show background tasks")
        console.print("/stop      Choose background tasks to stop")
        console.print("/model      Select model and thinking strength")
        console.print("/view \\[toggle|concise|full] Hide or show reasoning transcript text")
        console.print("/input-suggestion Toggle input suggestions")
        console.print("/status     Show status, usage, and DeepSeek balance")
        console.print("/theme      Show or change UI theme")
        console.print("/ui         Show or change Classic/Modern UI")
        console.print("/reset      Delete config and run setup again")
        console.print("/sessions   List project sessions")
        console.print("/resume ID  Resume a session")
        console.print("/compact \\[focus] Compact active session context")
        console.print("/new        Start a new session")
        console.print("/exit       Quit")
        return current_session_id
    if command.name == "new":
        loaded_skill_names.clear()
        console.print("Started a new session.")
        return None
    if command.name == "resume":
        entries = _resolve("list_session_entries")(project_root)
        previews = _build_resume_session_previews(project_root, entries)
        if command.argument:
            selected = resolve_session_selection(entries, command.argument)
            session_id = selected.id if selected is not None else command.argument
            _resume_session(console, project_root, session_id, palette=palette, settings=settings)
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
            style = palette.error if invalid_selection else palette.muted
            console.print(f"[{style}]{message}[/]")
            return current_session_id
        _resume_session(console, project_root, selected.id, palette=palette, settings=settings)
        return selected.id
    if command.name == "sessions":
        entries = _resolve("list_session_entries")(project_root)
        if not entries:
            console.print("No sessions found.")
            return current_session_id
        for entry in entries:
            console.print(
                f"{entry.id}\tupdated={entry.updated_at}\thistory_estimate={entry.active_tokens}\t"
                f"{format_usage_line(entry.usage)}\tcache={_format_session_cache_for_list(entry)}"
            )
        return current_session_id
    if command.name == "status":
        balance = (
            _resolve("fetch_deepseek_balance")(settings)
            if supports_session_cost(settings)
            else BalanceStatus(unavailable_reason="unsupported provider")
        )
        console.print(
            format_compact_status_report(
                build_status_report(
                    project_root,
                    settings,
                    current_session_id=current_session_id,
                    balance=balance,
                )
            )
        )
        return current_session_id
    if command.name == "mcp":
        startup_snapshot = startup_state.snapshot() if startup_state is not None else None
        if startup_snapshot is not None and startup_snapshot.mcp_pending:
            console.print("MCP: connecting.")
            return current_session_id
        statuses = mcp_runtime.statuses if mcp_runtime is not None else []
        if startup_snapshot is not None and startup_snapshot.mcp_failed and not statuses:
            console.print("MCP: startup failed.")
            return current_session_id
        console.print(format_mcp_status(statuses))
        return current_session_id
    if command.name == "ps":
        console.print(_format_background_tasks_for_terminal(background_tasks, active_only=False))
        return current_session_id
    if command.name == "stop":
        console.print(
            _stop_background_tasks_for_terminal(
                background_tasks,
                selection=command.argument,
                input_func=input_func,
                console=console,
            )
        )
        return current_session_id
    if command.name == "compact":
        return _handle_compact_command(
            command,
            console,
            project_root,
            current_session_id,
            settings,
            palette,
        )
    if command.name == "model":
        return _handle_model_command(
            command,
            console,
            current_session_id,
            settings,
            palette,
            input_func=input_func,
        )
    if command.name == "view":
        return _handle_view_command(command, console, current_session_id, settings, palette)
    if command.name == "input-suggestion":
        return _handle_input_suggestion_command(command, console, current_session_id, settings, palette)
    if command.name == "theme":
        return _handle_theme_command(
            command,
            console,
            current_session_id,
            settings,
            palette,
            input_func=input_func,
        )
    if command.name == "ui":
        return _handle_ui_command(command, console, current_session_id, settings, palette, input_func=input_func)
    if command.name == "reset":
        return _handle_reset_command(console, current_session_id, settings, palette)
    if command.name == "skills":
        return _handle_skills_command(
            command,
            console,
            project_root,
            current_session_id,
            loaded_skill_names,
            palette,
        )
    if command.name.startswith("skill:"):
        skill_name = command.name.removeprefix("skill:")
        skill = find_skill(project_root, skill_name)
        if skill is None:
            console.print(f"[{palette.error}]Skill not found:[/] {skill_name}")
            return current_session_id
        console.print(f"[{palette.error}]Cannot run /skill:{skill.name} from this handler.[/]")
        return current_session_id

    console.print(f"[{palette.error}]Unknown command:[/] /{command.name}")
    return current_session_id


def _handle_compact_command(
    command: SlashCommand,
    console: Console,
    project_root: Path,
    current_session_id: str | None,
    settings: Settings,
    palette: UiPalette,
) -> str | None:
    if not current_session_id:
        console.print(f"[{palette.muted}]No active session to compact.[/]")
        return current_session_id
    session = DeepySession.open(project_root, current_session_id)
    try:
        items = asyncio.run(session.get_items())
    except Exception as exc:
        console.print(f"[{palette.error}]Failed to read session:[/] {exc}")
        return current_session_id
    if not items:
        console.print(f"[{palette.muted}]The context is empty.[/]")
        return current_session_id
    console.print(f"[{palette.muted}]Compacting context...[/]")
    manager = DeepySessionManager(project_root=project_root, settings=settings, active_session_id=current_session_id)
    try:
        result = asyncio.run(
            manager.compact_session(
                current_session_id,
                focus_instruction=command.argument or None,
            )
        )
    except ContextCompactionError as exc:
        console.print(f"[{palette.error}]Compact failed:[/] {exc}")
        console.print(f"[{palette.muted}]Original session left unchanged.[/]")
        return current_session_id
    except Exception as exc:
        console.print(f"[{palette.error}]Compact failed:[/] {exc}")
        console.print(f"[{palette.muted}]Original session left unchanged.[/]")
        return current_session_id
    if not result.compacted:
        console.print(f"[{palette.muted}]{result.message or 'There is no context to compact.'}[/]")
        return current_session_id
    console.print(
        f"[{palette.info}]Context compacted:[/] "
        f"{result.before_tokens:,} -> {result.after_tokens:,} tokens · "
        f"preserved {result.preserved_item_count} items"
    )
    return current_session_id


def _resume_session(
    console: Console,
    project_root: Path,
    session_id: str,
    *,
    palette: UiPalette | None = None,
    settings: Settings | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    console.print(Text.assemble(("Resuming session ", palette.muted), (session_id, palette.info)))
    _print_session_history(console, project_root, session_id, palette=palette, settings=settings)


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


def _print_session_history(
    console: Console,
    project_root: Path,
    session_id: str,
    *,
    palette: UiPalette | None = None,
    settings: Settings | None = None,
) -> None:
    palette = palette or DARK_PALETTE
    items = _load_session_items(project_root, session_id)
    if not items:
        console.print(f"[{palette.muted}]No visible history for this session.[/]")
        return

    console.print(Text("History", style=f"bold {palette.muted}"))
    renderer = TerminalStreamRenderer(
        console,
        project_root=str(project_root),
        palette=palette,
        view_mode=settings.ui.view_mode if settings is not None else "concise",
    )
    for item in items:
        _print_history_item(console, item, renderer, palette=palette)
    renderer.flush()


def _print_history_item(
    console: Console,
    item: dict[str, Any],
    renderer: TerminalStreamRenderer,
    *,
    palette: UiPalette | None = None,
) -> None:
    palette = palette or DARK_PALETTE
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
        _print_user_input(console, _item_text(item), palette=palette)
        return

    if role == "assistant":
        text = _item_text(item)
        tool_calls = _chat_tool_calls(item)
        if text.strip():
            renderer.flush()
            _print_assistant_output(console, text, palette=palette)
        for tool_call in tool_calls:
            renderer(_history_tool_call_event(tool_call))
        return


def _history_tool_output_event(item: dict[str, Any]) -> DeepyStreamEvent:
    return history_tool_output_event(item, _tool_output_text)


def _load_session_items(project_root: Path, session_id: str) -> list[dict[str, Any]]:
    try:
        return asyncio.run(DeepySession.open(project_root, session_id).get_items())
    except Exception:
        return []


def _session_title(items: list[dict[str, Any]]) -> str:
    return session_title(items, _item_text)


def _session_status(items: list[dict[str, Any]]) -> str:
    return session_status(items, _tool_output_text)


