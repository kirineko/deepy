## Search

Search local project files without shell `grep`, `find`, or `rg`.

Args: `query`, `path`, `glob`, `mode`, `output_mode`, `case_sensitive`,
`context`, `limit`, `offset`, `include_ignored`.

Use `Search` for repository code/text search before falling back to `shell`.
It is built into Deepy and does not require ripgrep or platform-specific shell
commands. It is read-only.

Defaults and guidance:
- Use `mode: "literal"` unless the user clearly needs a regex.
- Use `output_mode: "files"` for broad discovery, then `Read` specific
  files or rerun with `output_mode: "content"`.
- Use `output_mode: "count"` to understand match distribution.
- Use `glob` or a narrower `path` to keep results focused.
- Use `limit` and `offset` to page through large result sets.
- Leave `include_ignored` false unless ignored build artifacts or dependencies
  are explicitly relevant. Sensitive files are still filtered.
