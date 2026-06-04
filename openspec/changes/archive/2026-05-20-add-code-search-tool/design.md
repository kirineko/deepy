## Context

Deepy currently exposes read, edit, write, patch, shell, web, skill, question,
and todo tools through the OpenAI Agents SDK. Repository search is still left to
the model through shell commands, which makes behavior depend on whether the
runtime has `rg`, `grep`, or compatible shell syntax available.

The desired direction is a first-class `Search` tool that is efficient enough
for normal codebase exploration, works on Windows without requiring users to
install ripgrep, and keeps output bounded for model context. `ripgrep-python`
was investigated but is not in scope because it still requires ripgrep as a
dependency. The proposed implementation uses Deepy's own Python search backend
with `regex` and `pathspec` as lightweight dependencies.

## Goals / Non-Goals

**Goals:**

- Provide a model-facing `Search` tool for fast code/text search under the
  current project.
- Make the default backend fully available from Deepy's Python package without
  requiring a system `rg` executable.
- Prefer literal string search by default, with regex search available only when
  requested.
- Respect project boundaries, gitignore-style filtering, sensitive-file
  protections, and binary/large-file limits.
- Keep results token-aware through output modes, limits, offsets, truncation
  metadata, and concise UI summaries.
- Preserve Windows support, including path handling and text decoding for common
  encodings already handled by Deepy's file tools.

**Non-Goals:**

- Exact feature parity with ripgrep.
- Requiring users to install `rg`, `grep`, Git Bash, WSL, or other external
  search tools.
- Adding `ripgrep-python` as a dependency.
- Searching outside the current project by default.
- Indexing the repository persistently in the first version.
- Replacing `WebSearch`; `Search` is for local project files only.

## Decisions

### Use a Python search engine as the default backend

Deepy will implement traversal, filtering, matching, result formatting, and
pagination in Python. This makes the tool reliable on Windows and in minimal
environments where shell tools are absent or inconsistent.

Alternatives considered:

- System `rg`: fastest, but violates the no-external-tool constraint.
- Bundled `rg`: avoids user installation but complicates packaging,
  architecture selection, signing, updates, and wheel size.
- `ripgrep-python`: not in scope because it still depends on ripgrep.

### Add `regex` and `pathspec`

`regex` gives Deepy timeout-capable regular expression matching and better
control than Python's standard `re` for potentially expensive model-provided
patterns. `pathspec` gives more complete `.gitignore`-style matching than the
current simplified matcher in `builtin.py`.

Alternatives considered:

- Standard `re`: avoids a dependency but lacks robust per-match timeout support.
- Custom gitignore matcher only: already exists in Deepy, but does not aim for
  full gitignore semantics.
- RE2/Hyperscan bindings: attractive for specific performance/safety profiles
  but introduce platform and wheel availability concerns.

### Default to literal search

The `Search` tool will default to literal mode because model search queries are
usually identifiers, string snippets, or filenames, not deliberate regexes.
Regex mode remains available through an explicit parameter.

Alternatives considered:

- Default regex mode: closer to grep tools but more error-prone for model calls
  containing braces, brackets, dots, or backslashes.
- Auto-detect regex: ambiguous and hard to explain in tool results.

### Support three output modes

The tool will support:

- `files`: matching file paths only.
- `content`: matching lines with optional context.
- `count`: match counts per file and aggregate totals.

This mirrors the useful modes from ripgrep-oriented tools while letting the
model start broad and then narrow follow-up reads.

### Bound work and output independently

Search execution will enforce both work limits and output limits:

- skip known high-noise directories unless explicitly included,
- skip binary and unsupported large files,
- cap scanned file size,
- cap result count/bytes,
- return `next_offset` for pagination,
- include metadata about truncation and skipped files.

This prevents Search from becoming a context-overflow source.

### Reuse Deepy's existing tool surfaces

`Search` will be registered beside existing FunctionTools, return normal
`ToolResult` JSON, use `[Search]` as the display label, and include concise
tool-call summaries. The tool stays read-only and does not participate in the
file mutation snapshot/write path.

## Risks / Trade-offs

- [Risk] Pure Python search will be slower than ripgrep on very large
  repositories. → Mitigation: use literal mode by default, prune ignored/noisy
  directories early, add limits, and guide models to narrow `path`/`glob`.
- [Risk] Regex patterns from the model can be expensive. → Mitigation: use
  `regex` timeouts, catch timeout errors, and return structured diagnostics.
- [Risk] `.gitignore` behavior can surprise users if incomplete. → Mitigation:
  use `pathspec`, test common gitignore cases, and expose `include_ignored`.
- [Risk] Search results may expose secrets. → Mitigation: filter sensitive file
  names and avoid returning sensitive file content even when ignored files are
  included.
- [Risk] Cross-platform decoding can differ from file reading. → Mitigation:
  reuse Deepy's text metadata decoding path where practical and add Windows
  encoding regression tests.
- [Risk] Adding dependencies increases package surface. → Mitigation: keep the
  dependencies lightweight and covered by normal release validation.
