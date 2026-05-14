## modify

Create new files or edit existing files.

Use `content` only when the target file does not exist. For existing files, read the
file first, then use `old_string` and `new_string` for the smallest reliable
replacement. Do not rewrite an existing scaffolded file with full content; replace the
specific generated block instead.

Args for new files: `file_path`, `content`.

Args for existing files: `file_path`, `old_string`, `new_string`, optional
`replace_all`, optional `snippet_id`.

Existing files must be read before editing. Stale edits are rejected. Repeated matches
are rejected unless `replace_all` is true; candidate snippets can be reused with
`snippet_id`. Success includes diff metadata.

If several `old_string` attempts fail and you know the complete desired file content,
re-read the file and use the managed whole-file replacement path. Do not delete the file
and recreate it with shell commands or here-strings; that bypasses Deepy's encoding,
newline, and stale-write protections, especially on Windows.
