## Update

Apply exact text replacements to one or more files.

Args:
- Single edit: `path`, `old`, `new`.
- Multiple edits in one file: `path`, `edits: [{old, new}]`.
- Multiple files: `edits: [{path, old, new}]`.
- Optional `replace_all` and `expected_occurrences`.

Use `Update` for existing code, tests, docs, and config when the current text is
known. The `old` text is whitespace-sensitive plain text and must match exactly.
For broad replacements, use `replace_all=true` with `expected_occurrences`.

Deepy stages and validates all edits in a call before writing. If any edit is
stale, missing, ambiguous, count-mismatched, unsupported, or a no-op, no file is
changed and the result identifies the failing edit.
