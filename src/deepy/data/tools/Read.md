## Read

Read one or more files or directories.

Args:
- `path`: single target path.
- `files`: array of read targets for batch reads.
- Optional range controls: `range` (`"20-80"`), `head`, `tail`, `offset`, `limit`.
- Optional `pages` for PDF page ranges.

Use `Read` before replacing an existing whole file with `Write`, and whenever
you need exact context for `Update`. When several files are relevant, prefer one
batch call with `files` instead of serial single-file reads.

Text output includes line numbers and total line metadata. Successful text reads
record runtime-managed read state for later `Write` or `Update`; the model does
not need to copy snapshot ids, tokens, or content hashes.
