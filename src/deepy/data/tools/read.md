## read

Inspect files or list directories before changes.

Args: `path`, optional `start_line`, `limit`.

Text output includes line numbers. Directory output lists entries. Reads record file state so
later `write`/`edit` can detect stale changes.
