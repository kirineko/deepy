from __future__ import annotations

from ..result import ToolResult
from ..shell_command import (
    _background_task_output_metadata,
    _background_task_payload,
    _format_background_task_line,
    _format_background_task_output,
)
from .state import ToolRuntimeState


class TaskToolsMixin(ToolRuntimeState):
    def task_list(self, *, active_only: bool = False, limit: int = 20) -> str:
        snapshots = self.background_tasks.list(active_only=active_only, limit=max(1, limit))
        if snapshots:
            lines = [
                _format_background_task_line(snapshot)
                for snapshot in snapshots
            ]
            output = "\n".join(lines)
        elif active_only:
            output = "No running background tasks."
        else:
            output = "No background tasks."
        return ToolResult.ok_result(
            "task_list",
            output,
            metadata={
                "kind": "background_task_list",
                "activeOnly": active_only,
                "tasks": [_background_task_payload(snapshot) for snapshot in snapshots],
            },
        ).to_json()

    def task_output(
        self,
        task_id: str,
        *,
        block: bool = False,
        timeout: int = 3,
    ) -> str:
        name = "task_output"
        if block:
            self.background_tasks.wait_for_output(task_id, timeout_seconds=max(0, min(timeout, 5)))
        output = self.background_tasks.read_output(task_id)
        if output is None:
            return ToolResult.error_result(
                name,
                f"Background task not found: {task_id}",
                metadata={
                    "kind": "background_task_output",
                    "error_code": "background_task_not_found",
                    "taskId": task_id,
                },
            ).to_json()
        return ToolResult.ok_result(
            name,
            _format_background_task_output(output),
            metadata=_background_task_output_metadata(output),
        ).to_json()

    def task_stop(self, task_id: str) -> str:
        name = "task_stop"
        snapshot = self.background_tasks.stop(task_id)
        if snapshot is None:
            return ToolResult.error_result(
                name,
                f"Background task not found: {task_id}",
                metadata={
                    "kind": "background_task_stop",
                    "error_code": "background_task_not_found",
                    "taskId": task_id,
                },
            ).to_json()
        return ToolResult.ok_result(
            name,
            f"Stop requested for background task {snapshot.id} ({snapshot.status}).",
            metadata={
                "kind": "background_task_stop",
                "task": _background_task_payload(snapshot),
            },
        ).to_json()
