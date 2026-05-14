## write

Create a new file or explicit whole-file replacement.

Prefer `edit` over `write` for existing targeted changes: code, tests, imports,
comments, blocks, or lines. Do not rewrite an existing file just because final content
is known; preserve surrounding user changes with `edit`.

Args: `path`, `content` (complete file content).

Existing files must be read first. If rejected for unread state, read and usually switch
to `edit` unless a full rewrite was requested. Stale writes are rejected. Success includes diff.

Use this managed path for intentional whole-file replacement when exact edit matching
keeps failing and the complete final content is known. Do not delete and recreate files
with shell commands or here-strings, especially for Unicode text on Windows.
