## Context

Deepy's managed `modify(content=...)` and `write(...)` paths choose an encoding
when creating a new text file. The current Windows behavior writes new files as
`utf8-sig` whenever the content contains non-ASCII characters. That was intended
to help Windows editors identify Unicode text, but it applies too broadly:
source files created with non-ASCII comments or strings can begin with U+FEFF and
fail validation paths that parse source text read with plain `utf-8`.

Existing-file edits already preserve the detected encoding. That behavior is
valuable and should remain unchanged.

## Goals / Non-Goals

**Goals:**

- Create new managed text files as plain UTF-8 without a signature on Windows,
  macOS, and Linux.
- Prevent BOM-related failures in code, config, and project text files created
  by `modify`.
- Preserve detected encodings when editing existing files, including existing
  UTF-8 with signature, UTF-16, GBK-compatible, and plain UTF-8 files.
- Keep newline normalization and stale-write protections unchanged.

**Non-Goals:**

- Add a new public `encoding` parameter to `modify` or `write`.
- Convert existing UTF-8 signature files to plain UTF-8 during ordinary edits.
- Add special CSV export behavior. CSV/Excel compatibility can be handled later
  by an explicit export feature or user-directed workflow.
- Change shell output decoding or PowerShell command wrapping.

## Decisions

### Default new text files to plain UTF-8 everywhere

New text files should use `utf8` regardless of platform or Unicode content. The
main default use case for `modify` is project file creation: source code,
configuration, documentation, scripts, and structured text. Plain UTF-8 is the
least surprising and most tool-compatible default for those files.

Alternative considered: keep Windows non-ASCII files as `utf8-sig`. This keeps
maximum compatibility with legacy Windows consumers, but it breaks common code
validation paths and makes a Windows-only default leak into cross-platform
project files.

Alternative considered: choose by file extension. This would avoid BOM in code
while preserving it for some user-facing text, but it adds policy complexity and
still leaves ambiguous project files such as Markdown or generated assets. A
single plain UTF-8 default is easier to explain, test, and reason about.

### Preserve existing encoding on edits

The new default only applies when a file does not exist. If Deepy reads or edits
an existing text file, it should continue writing back with the detected
encoding. This protects user files and avoids surprising format churn.

Alternative considered: normalize existing UTF-8 signature files to plain UTF-8.
That would remove BOM over time, but it would weaken the current preservation
contract and create unrelated diffs.

### Keep explicit byte writes

The previous Windows CRLF fix changed writes to encode bytes explicitly instead
of relying on platform text mode. This should stay in place. The change is only
the selected encoding for new files, not the write mechanism.

## Risks / Trade-offs

- Legacy Windows tools or Excel CSV double-click workflows may prefer a UTF-8
  signature -> Treat those as explicit export/consumer requirements rather than
  the default for all project files.
- Users with existing UTF-8 signature files may still see BOM preserved after an
  edit -> This is intentional to avoid silent format conversion; users can
  request an explicit conversion if needed.
- Some documentation around Windows editor readability may become stale ->
  Update the tools spec and tests in the same change so the contract is clear.
