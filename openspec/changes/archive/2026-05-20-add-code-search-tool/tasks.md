## 1. Dependencies And Search Engine Structure

- [x] 1.1 Add `regex` and `pathspec` runtime dependencies and refresh the lockfile.
- [x] 1.2 Create a search-engine module with data models for requests, matches, summaries, skipped files, and result pages.
- [x] 1.3 Define constants for default limits, scan byte caps, noisy directories, sensitive names, and supported output modes.

## 2. Traversal, Filtering, And Decoding

- [x] 2.1 Implement project-root path resolution and reject search paths outside the current project.
- [x] 2.2 Implement `pathspec`-backed gitignore-style filtering with `include_ignored` support.
- [x] 2.3 Reuse or align with Deepy's text decoding behavior for UTF-16LE, UTF-8 BOM, UTF-8, and GB18030 text.
- [x] 2.4 Skip binary, unsupported, sensitive, and oversized files with structured skipped-file metadata.
- [x] 2.5 Apply glob filtering against project-relative paths using consistent POSIX-style separators.

## 3. Matching And Result Formatting

- [x] 3.1 Implement literal search as the default mode using efficient string scanning.
- [x] 3.2 Implement regex search using `regex` with timeout handling and structured invalid-pattern errors.
- [x] 3.3 Implement `files`, `content`, and `count` output modes.
- [x] 3.4 Implement content context lines, line numbers, per-file grouping, and stable project-relative paths.
- [x] 3.5 Implement `limit`/`offset` pagination, output byte caps, truncation notices, and `next_offset` metadata.

## 4. Tool Runtime And Agents SDK Integration

- [x] 4.1 Add `ToolRuntime.search(...)` returning standard `ToolResult` JSON.
- [x] 4.2 Add a strict `Search` FunctionTool schema and invocation adapter in `src/deepy/tools/agents.py`.
- [x] 4.3 Add `src/deepy/data/tools/Search.md` and include it in loaded tool documentation.
- [x] 4.4 Update system/tool guidance so models prefer `Search` over shell `grep`, `find`, or `rg` for local repository search.

## 5. UI And Session Display

- [x] 5.1 Add `[Search]` to tool display labels.
- [x] 5.2 Render concise Search argument summaries with query, path, and optional glob/filter.
- [x] 5.3 Ensure Search output summaries show result counts, truncation, and errors without raw JSON argument noise.

## 6. Tests And Validation

- [x] 6.1 Add unit tests for literal search, regex search, invalid regex, and regex timeout behavior.
- [x] 6.2 Add unit tests for gitignore/pathspec filtering, `include_ignored`, glob filtering, and noisy directory pruning.
- [x] 6.3 Add unit tests for `files`, `content`, and `count` output modes with pagination metadata.
- [x] 6.4 Add unit tests for binary, oversized, sensitive, and unsupported file skipping.
- [x] 6.5 Add Windows-focused tests for path separators, CRLF, UTF-16LE, UTF-8 BOM, UTF-8, and GB18030 text.
- [x] 6.6 Add Agents SDK/tool schema tests confirming `Search` is registered and old file-tool aliases remain absent.
- [x] 6.7 Add message-view tests for `[Search]` labels and concise parameter summaries.
- [x] 6.8 Run focused tests, full `uv run pytest -q`, `uv run ruff check`, `uv run ty check src`, and `openspec validate add-code-search-tool --type change --strict`.
