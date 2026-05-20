## read_file

Read files or list directories before changes.

Args: `file_path`, optional `offset`, optional `limit`, optional `pages`.

Text output includes line numbers. Full text reads record a managed snapshot with
encoding, line-ending, snapshot id, and content hash metadata for later
`edit_text`, `write_file`, or `apply_patch` calls. Partial reads return snippet
metadata that can scope later `edit_text` calls but do not authorize unrestricted
whole-file replacement. For normal single-file exact edits after a partial read,
prefer `edit_text` with `file_path` and no `snippet_id`; use the snippet only
when you need to constrain the replacement to that line range.

Non-text files such as images, notebooks, and PDFs may return descriptive
metadata, but they are not tracked for text mutation.
