## write

Use `write` to create a new file or replace an existing file.

Parameters:

- `path`: File path to write.
- `content`: Complete file content.

Safety rules:

- Existing files must be read before writing.
- If an existing file changed since it was read, the write is rejected.
- Successful writes include a diff in metadata.
