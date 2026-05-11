from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from deepy.config import Settings
from deepy.llm.events import DeepyStreamEvent
from deepy.llm.runner import RunSummary, run_prompt_once
from deepy.sessions import DeepyJsonlSession, SessionEntry, list_session_entries
from deepy.skills import discover_skills, find_skill, format_skills_for_terminal, read_skill_body
from deepy.status import build_status_report, format_status_report
from deepy.ui.ask_user_question import OTHER_VALUE
from deepy.ui.ask_user_question import AskUserQuestionItem
from deepy.ui.ask_user_question import AskUserQuestionOptionEntry
from deepy.ui.ask_user_question import build_answer_for_question
from deepy.ui.ask_user_question import build_options
from deepy.ui.ask_user_question import format_ask_user_question_answers
from deepy.ui.ask_user_question import format_ask_user_question_decline
from deepy.ui.ask_user_question import normalize_questions
from deepy.ui.exit_summary import build_exit_summary_text
from deepy.ui.message_view import format_tool_output_summary, tool_diff_preview
from deepy.ui.session_list import format_session_choices, resolve_session_selection


RunOnce = Callable[..., Awaitable[RunSummary]]
InputFunc = Callable[[str], str]


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
        if summary.status == "waiting_for_user":
            response = _collect_pending_question_response(output, summary.pending_questions)
            if response:
                summary = asyncio.run(
                    run_once(
                        response,
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
        if command.argument:
            selected = resolve_session_selection(entries, command.argument)
            session_id = selected.id if selected is not None else command.argument
            console.print(f"Resuming session {session_id}")
            return session_id
        if not entries:
            console.print("No sessions found.")
            return current_session_id
        console.print(format_session_choices(entries))
        chooser = input_func or (lambda prompt: Prompt.ask(prompt))
        selection = chooser("Resume session number or id")
        selected = resolve_session_selection(entries, selection)
        if selected is None:
            console.print("[red]Invalid session selection.[/red]")
            return current_session_id
        console.print(f"Resuming session {selected.id}")
        return selected.id
    if command.name == "sessions":
        entries = list_session_entries(project_root)
        if not entries:
            console.print("No sessions found.")
            return current_session_id
        for entry in entries:
            console.print(f"{entry.id}\tupdated={entry.updated_at}\ttokens={entry.active_tokens}")
        return current_session_id
    if command.name == "status":
        console.print(format_status_report(build_status_report(project_root, settings)))
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


def _print_stream_event(console: Console, event: DeepyStreamEvent) -> None:
    if event.kind in {"text_delta", "message"}:
        return
    if event.kind == "tool_call":
        tool_name = event.name or "tool"
        console.print(f"\n[dim]tool call:[/dim] {tool_name}")
        return
    if event.kind == "tool_output":
        summary = format_tool_output_summary(event.text)
        console.print(f"\n[dim]tool output:[/dim] {summary}")
        diff = tool_diff_preview(event.text)
        if diff:
            console.print(diff.rstrip())
        return
    if event.kind == "agent_updated" and event.name:
        console.print(f"\n[dim]agent:[/dim] {event.name}")


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
