## edit

Use `edit` to replace existing text in a file after reading that file first.

Parameters:

- `path`: File path to edit.
- `old`: Exact text to replace.
- `new`: Replacement text.
- `replace_all`: Whether to replace every exact occurrence.
- `snippet_id`: Optional snippet returned by a partial `read`, used to scope the replacement.

Safety rules:

- The file must be read before editing.
- If the file changed since it was read, the edit is rejected.
- Ambiguous repeated matches are rejected unless `replace_all` is true. The error metadata includes candidate snippets that can be used with `snippet_id`.
- If exact text is missing, Deepy may match simple over-escaped quotes/backslashes or return closest-match metadata with a snippet for follow-up.
- Successful edits include a diff in metadata.
