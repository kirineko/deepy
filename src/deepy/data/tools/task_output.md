## task_output

Read captured stdout/stderr for a Deepy-managed background shell task.

Args: `task_id`, optional `block`, optional `timeout`.

Use `block=true` with a small timeout when startup output is expected. Deepy
waits only until output appears, the task exits, or the bounded timeout expires;
it does not wait for long-running servers or watchers to finish. The result
returns a bounded tail of the task log plus size metadata, and indicates when
earlier output is available but not included.
