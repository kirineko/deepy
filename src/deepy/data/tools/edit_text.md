## edit_text

Make a small exact/string edit to an existing text file.

Args: `file_path`, `old_string`, `new_string`, `replace_all`,
`expected_occurrences`, optional `snippet_id`.

Use this for focused edits where the current text is known. Prefer
`expected_occurrences` as a safety check, especially with `replace_all`. If a
partial `read_file` returned a `snippet_id`, pass it only when you intentionally
want to restrict the replacement to that snippet. For ordinary single-file exact
edits, pass `file_path` and omit `snippet_id`; Deepy can internally promote a
fresh partial read to a full-file exact edit when needed. Do not pass
`snapshot_id` as `snippet_id`; snapshots are for stale protection, while
snippets are only returned by partial reads.

Deepy preserves the existing file encoding and line endings, rejects stale files,
rejects no-op edits, and returns structured error metadata for missing,
ambiguous, or count-mismatched replacements. Use `apply_patch` when there are
multiple edits in one file, multiple files, create/delete/move operations, or a
larger block replacement.
