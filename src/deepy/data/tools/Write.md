## Write

Create a new text file or replace a whole existing text file.

Args:
- `path`: target file path.
- `content`: complete file content.
- `overwrite`: set to `true` only for intentional existing-file replacement.

For existing files, call `Read` first so Deepy can verify the file is fresh
before replacement. Use `Update` for exact targeted edits instead of rewriting a
whole file.
