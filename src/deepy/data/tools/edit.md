## edit

Replace existing text after reading the file first.

Prefer `edit` over `write` for existing files when changing specific code, tests, imports,
comments, blocks, or lines; it keeps changes scoped and reviewable.

Args: `path`, `old`, `new`, optional `replace_all`, optional `snippet_id`.

The file must be read first. Stale files are rejected. Repeated matches are rejected unless
`replace_all` is true; candidate snippets can be reused with `snippet_id`. If exact text is
missing, simple over-escaping may be corrected or closest-match metadata returned. Success
includes diff metadata.

After repeated `old_string not found` failures, re-read the file. If you know the complete
intended content, switch to the managed whole-file replacement path instead of deleting
the file or recreating it through shell commands.
