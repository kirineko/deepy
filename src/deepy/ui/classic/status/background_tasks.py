from __future__ import annotations

from collections.abc import Callable, Sequence

from rich.console import Console

from deepy.background_tasks import BackgroundTaskManager, BackgroundTaskSnapshot

InputFunc = Callable[[str], str]


def _format_background_tasks_for_terminal(
    background_tasks: BackgroundTaskManager | None,
    *,
    active_only: bool = False,
) -> str:
    if background_tasks is None:
        return "Background task management is not available in this UI."
    tasks = background_tasks.list(active_only=active_only)
    if not tasks:
        return "No running background tasks." if active_only else "No background tasks."
    return "\n".join(_format_background_task_for_terminal(task) for task in tasks)


def _format_background_task_for_terminal(task: BackgroundTaskSnapshot) -> str:
    pid = f" pid={task.pid}" if task.pid is not None else ""
    exit_code = f" exit={task.exit_code}" if task.exit_code is not None else ""
    stopped = " stop_requested" if task.stop_requested else ""
    return f"{task.id}\t{task.status}{pid}{exit_code}{stopped}\t{task.command}"


def _stop_background_tasks_for_terminal(
    background_tasks: BackgroundTaskManager | None,
    *,
    selection: str = "",
    input_func: InputFunc | None = None,
    console: Console | None = None,
) -> str:
    if background_tasks is None:
        return "Background task management is not available in this UI."
    running_tasks = background_tasks.list(active_only=True)
    if not running_tasks:
        return "No running background tasks."
    resolved_selection = _resolve_background_stop_selection(
        running_tasks,
        selection=selection,
        input_func=input_func,
        console=console,
    )
    if resolved_selection is None:
        return "Stop canceled."
    if resolved_selection == "__invalid__":
        return "Invalid background task selection."
    if resolved_selection == "all":
        return _stop_all_background_tasks_for_terminal(background_tasks)
    snapshot = background_tasks.stop(resolved_selection, force_after_grace=True)
    if snapshot is None:
        return f"Background task not found: {resolved_selection}"
    return f"Stop requested for background task {snapshot.id}."


def _resolve_background_stop_selection(
    running_tasks: Sequence[BackgroundTaskSnapshot],
    *,
    selection: str = "",
    input_func: InputFunc | None = None,
    console: Console | None = None,
) -> str | None:
    selected = selection.strip()
    if selected:
        return _parse_background_stop_selection(running_tasks, selected)
    if input_func is None:
        return "all"
    choices = ["Running background tasks:"]
    choices.extend(
        f"{index}. {_format_background_task_for_terminal(task)}"
        for index, task in enumerate(running_tasks, start=1)
    )
    choices.append(f"{len(running_tasks) + 1}. all\tStop all running background tasks")
    choices.append(f"{len(running_tasks) + 2}. cancel\tReturn without stopping tasks")
    if console is not None:
        console.print("\n".join(choices))
    prompt = "Stop background task number, id, or Esc to cancel"
    response = input_func(prompt)
    return _parse_background_stop_selection(running_tasks, response.strip())


def _parse_background_stop_selection(
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


def _stop_all_background_tasks_for_terminal(background_tasks: BackgroundTaskManager) -> str:
    summary = background_tasks.stop_all(force_after_grace=True)
    count = len(summary.stopped)
    task_label = "task" if count == 1 else "tasks"
    return f"Stop requested for {count} background {task_label}."
