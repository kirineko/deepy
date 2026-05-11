## edit

Use `edit` to replace existing text in a file after reading that file first.

Parameters:

- `path`: File path to edit.
- `old`: Exact text to replace.
- `new`: Replacement text.
- `replace_all`: Whether to replace every exact occurrence.

Safety rules:

- The file must be read before editing.
- If the file changed since it was read, the edit is rejected.
- Ambiguous repeated matches are rejected unless `replace_all` is true.
- Successful edits include a diff in metadata.
