## task_stop

Request termination of a Deepy-managed background shell task.

Args: `task_id`.

Use this when a server, watcher, or long-running job is no longer needed. Deepy
tracks the stop request and updates the task status after the process exits.
When the user exits Deepy, remaining background tasks are stopped automatically.
