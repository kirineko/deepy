## task_list

List Deepy-managed background shell tasks that were started with
`shell(run_in_background=true)`.

Args: optional `active_only`, optional `limit`.

Use this before inspecting or stopping a background task when you need the task
id or current status. The output includes task ids, status, pid when available,
exit code when finished, and the original command. It never streams task output
into normal assistant thinking or response text.
