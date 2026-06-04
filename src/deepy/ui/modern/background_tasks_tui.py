"""Background-task formatting helpers for the Modern UI."""

from __future__ import annotations

from collections.abc import Sequence

from deepy.background_tasks import BackgroundTaskSnapshot


def _format_tui_background_task_details(task: BackgroundTaskSnapshot) -> str:
    details: list[str] = []
    if task.pid is not None:
        details.append(f"pid `{task.pid}`")
    if task.exit_code is not None:
        details.append(f"exit `{task.exit_code}`")
    if task.stop_requested:
        details.append("stop requested")
    return ", ".join(details)


def _format_tui_background_tasks_transcript(tasks: Sequence[BackgroundTaskSnapshot]) -> str:
    if not tasks:
        return "Background Tasks\nNo background tasks."
    lines = ["Background Tasks"]
    for index, task in enumerate(tasks, start=1):
        lines.append(f"{index}. {task.id} {task.status}: {task.command}")
        details = _format_tui_background_task_details(task)
        if details:
            lines.append(f"   {details}")
    lines.append("")
    lines.append("Use /stop <id>, /stop <number>, or /stop all.")
    return "\n".join(lines)


def _parse_tui_background_stop_selection(
    running_tasks: Sequence[BackgroundTaskSnapshot],
    selection: str,
) -> str | None:
    normalized = selection.strip()
    if not normalized:
        return None
    if normalized.lower() in {"cancel", "c", "q", "quit"}:
        return None
    if normalized.lower() in {"all", "a", "*"}:
        return "all"
    if normalized.isdigit():
        index = int(normalized) - 1
        if index == len(running_tasks):
            return "all"
        if index == len(running_tasks) + 1:
            return None
        if 0 <= index < len(running_tasks):
            return running_tasks[index].id
        return "__invalid__"
    if any(task.id == normalized for task in running_tasks):
        return normalized
    return "__invalid__"
