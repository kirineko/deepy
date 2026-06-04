## Why

Deepy currently lacks a model-facing code search tool, so models must fall back
to shell commands such as `grep`, `find`, or `rg` for common repository
investigation. That makes search behavior dependent on the user's platform and
installed tools, and it can produce unbounded output that is hard for the model
and terminal UI to consume.

This change adds a built-in, cross-platform `Search` tool that gives models a
fast, token-aware, read-only way to find code without requiring Windows users or
other environments to install ripgrep.

## What Changes

- Add a model-facing `Search` tool for code and text search inside the current
  project.
- Implement the default search backend inside Deepy rather than invoking an
  external `rg` binary or depending on `ripgrep-python`.
- Add lightweight Python dependencies for robust built-in search behavior:
  - `regex` for safer regex matching with timeout support.
  - `pathspec` for more complete `.gitignore`-style filtering.
- Support literal and regex search modes, with literal search as the default.
- Support result modes for matching content, matching files, and match counts.
- Add output pagination, truncation metadata, and concise UI summaries so large
  repositories do not flood model context or terminal output.
- Respect workspace path boundaries, ignored files, binary/large-file limits,
  and sensitive-file protections.
- Update tool guidance so models prefer `Search` over shell `grep`, `find`, or
  `rg` for repository search.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tools`: Add the built-in `Search` tool contract, behavior, output metadata,
  and model/tool-display guidance.

## Impact

- Tool runtime: add a read-only search execution path and supporting search
  engine helpers.
- Tool registration: expose `Search` through the OpenAI Agents SDK tool flow.
- Tool docs and prompt guidance: teach models when to use `Search` instead of
  shell commands.
- UI rendering: display `[Search]` calls with concise query/path summaries and
  readable result output.
- Dependencies: add `regex` and `pathspec` as lightweight runtime dependencies.
- Tests: add coverage for literal/regex search, ignore behavior, pagination,
  output modes, sensitive-file filtering, Windows paths/encodings, and large
  file limits.
