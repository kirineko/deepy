## read

Use `read` to inspect files or list directories before making changes.

Parameters:

- `path`: File or directory path.
- `start_line`: First line to read for text files.
- `limit`: Optional maximum number of lines.

Behavior:

- Text files are returned with line numbers.
- Directories are listed.
- Reads record file state so later `write` and `edit` calls can detect stale changes.
