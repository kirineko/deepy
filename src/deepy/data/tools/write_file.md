## write_file

Create a new text file or explicitly replace a whole file.

Args: `file_path`, `content`, `overwrite`, optional `snapshot_id`, optional
`expected_hash`.

For new files, Deepy writes UTF-8 without BOM by default. For existing files,
whole-file replacement requires `overwrite=true` and a fresh `snapshot_id` or
`expected_hash` from `read_file`; this prevents accidental stale rewrites.

Prefer `edit_text` for small targeted edits and `apply_patch` for structured or
multi-file edits.
