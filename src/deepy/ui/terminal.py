from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from deepy.config import Settings
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary, run_prompt_once
from deepy.sessions import list_session_entries
from deepy.skills import discover_skills, find_skill, format_skills_for_terminal, read_skill_body


RunOnce = Callable[..., Awaitable[RunSummary]]


@dataclass(frozen=True)
class SlashCommand:
    name: str
    argument: str = ""


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
) -> int:
    root = (project_root or Path.cwd()).resolve()
    output = console or Console()
    session_id: str | None = None

    output.print("[bold]Deepy[/bold] interactive mode")
    output.print(f"Project: {root}")
    output.print("Type /help for commands, /exit to quit.")
    loaded_skill_names: list[str] = []

    while True:
        try:
            text = Prompt.ask("[bold cyan]deepy[/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            output.print()
            return 0

        if not text:
            continue

        slash = parse_slash_command(text)
        if slash is not None:
            next_session = _handle_slash_command(slash, output, root, session_id, loaded_skill_names)
            if next_session == "__exit__":
                return 0
            session_id = next_session
            continue

        summary = asyncio.run(
            run_once(
                text,
                project_root=root,
                settings=settings,
                emit=lambda delta: output.print(delta, end=""),
                emit_event=lambda event: _print_stream_event(output, event),
                session_id=session_id,
                skill_names=list(loaded_skill_names),
            )
        )
        session_id = summary.session_id
        if summary.output and not summary.output.endswith("\n"):
            output.print()


def _handle_slash_command(
    command: SlashCommand,
    console: Console,
    project_root: Path,
    current_session_id: str | None,
    loaded_skill_names: list[str] | None = None,
) -> str | None:
    loaded_skill_names = loaded_skill_names if loaded_skill_names is not None else []
    if command.name in {"exit", "quit"}:
        return "__exit__"
    if command.name == "help":
        console.print("/help       Show commands")
        console.print("/skills     List available skills")
        console.print("/skill NAME Show a skill document")
        console.print("/use NAME   Load a skill for subsequent prompts")
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
        if not command.argument:
            console.print("[red]Usage:[/red] /resume SESSION_ID")
            return current_session_id
        console.print(f"Resuming session {command.argument}")
        return command.argument
    if command.name == "sessions":
        entries = list_session_entries(project_root)
        if not entries:
            console.print("No sessions found.")
            return current_session_id
        for entry in entries:
            console.print(f"{entry.id}\tupdated={entry.updated_at}\ttokens={entry.active_tokens}")
        return current_session_id
    if command.name == "skills":
        console.print(format_skills_for_terminal(discover_skills(project_root)))
        return current_session_id
    if command.name == "skill":
        if not command.argument:
            console.print("[red]Usage:[/red] /skill NAME")
            return current_session_id
        skill = find_skill(project_root, command.argument)
        if skill is None:
            console.print(f"[red]Skill not found:[/red] {command.argument}")
            return current_session_id
        console.print(read_skill_body(skill) or "(empty skill)")
        return current_session_id
    if command.name == "use":
        if not command.argument:
            console.print("[red]Usage:[/red] /use NAME")
            return current_session_id
        skill = find_skill(project_root, command.argument)
        if skill is None:
            console.print(f"[red]Skill not found:[/red] {command.argument}")
            return current_session_id
        if skill.name not in loaded_skill_names:
            loaded_skill_names.append(skill.name)
        console.print(f"Loaded skill: {skill.name}")
        return current_session_id

    console.print(f"[red]Unknown command:[/red] /{command.name}")
    return current_session_id


def _print_stream_event(console: Console, event: DeepyStreamEvent) -> None:
    if event.kind in {"text_delta", "message"}:
        return
    if event.kind == "tool_call":
        tool_name = event.name or "tool"
        console.print(f"\n[dim]tool call:[/dim] {tool_name}")
        return
    if event.kind == "tool_output":
        summary = _tool_output_summary(event.text)
        console.print(f"\n[dim]tool output:[/dim] {summary}")
        return
    if event.kind == "agent_updated" and event.name:
        console.print(f"\n[dim]agent:[/dim] {event.name}")


def _tool_output_summary(output: str) -> str:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return output[:160]
    if not isinstance(payload, dict):
        return output[:160]
    name = payload.get("name") or "tool"
    ok = payload.get("ok")
    error = payload.get("error")
    metadata = payload.get("metadata")
    path = metadata.get("path") if isinstance(metadata, dict) else None
    status = "ok" if ok else "failed"
    details = str(error or path or "").strip()
    return f"{name} {status}" + (f" - {details}" if details else "")
