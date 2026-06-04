## Design

`Write` and `Update` success output can include both a generic tool status line
and a diff preview header. The diff header already carries the useful
information for successful file mutations: operation label, changed path, and
added/removed line counts.

The renderer should therefore:

- Build the diff preview before adding the summary line.
- Omit the summary only when the parsed tool result is successful, the tool is
  `Write` or `Update`, and a diff preview is available.
- Keep the summary for failed, retryable, malformed, no-diff, and non-file
  mutation tool results.

Stable terminal streaming uses the same rule before printing the tool-output
progress line, so live output and transcript/history rendering remain
consistent.
