## Context

Stable terminal UI uses a bottom runtime status row during model and local
command work. A background refresh thread updates spinner and elapsed time while
stream events print thinking, tool calls, tool results, diffs, and shell output.
The bottom row writer currently truncates and pads by Python string length, but
other rendering code already uses display-cell width for CJK and wide
characters.

WebSearch is a good stress case: tool details can be long, include user query
text, and remain active long enough for repeated spinner/time refreshes. If
status writes interleave with transcript writes or the row is padded using the
wrong display width, the visible spinner/time area can appear slightly
corrupted.

## Goals / Non-Goals

**Goals:**

- Keep the stable runtime status row visually coherent during WebSearch,
  WebFetch, MCP, shell, and thinking states.
- Truncate and pad runtime status text by terminal display cells.
- Serialize bottom-status writes with transcript/tool output writes.
- Preserve recently archived bottom-anchor behavior on Windows and POSIX.
- Add unit tests that reproduce wide-character and long-tool-summary cases
  without requiring a real terminal.

**Non-Goals:**

- Do not redesign the status footer, toolbar content, or prompt layout.
- Do not change experimental Textual TUI rendering.
- Do not change tool result semantics, WebSearch behavior, or MCP integration.
- Do not reintroduce a multi-line fixed overlay.

## Decisions

### Fit the status row by display cells

Use Rich's display-cell helpers, or an equivalent shared helper, when truncating
and padding runtime status text. The final written line should occupy exactly
the reserved row width in display cells, including CJK query text and ellipsis.

Alternative considered: keep character-count truncation and shorten WebSearch
summaries. That would reduce some failures but would not fix wide-character
status text or other long tool names.

### Guard terminal writes with one shared lock

Introduce a stable terminal output coordination point so the background status
refresh cannot write ANSI cursor movement while the main thread is printing tool
output. The lock should cover raw bottom-row writes and normal transcript writes
that can occur during active status display.

Alternative considered: pause the refresh thread during each stream event. That
is harder to make complete and still leaves clear/update races around tool
output.

### Keep detail text concise at the status source

Runtime status should keep stable labels such as `thinking` and concise
`tool [WebSearch] query` detail. If detail text exceeds the terminal row, the
bottom writer remains the final guard, but source summaries should avoid dumping
tool output or full JSON.

## Risks / Trade-offs

- [Risk] Locking terminal writes can introduce deadlocks if a callback prints
  while holding the lock. -> Mitigation: keep the critical section narrow and
  avoid calling user callbacks inside it.
- [Risk] Cell-width truncation can split combining sequences if implemented by
  hand. -> Mitigation: prefer existing Rich cell helpers or a tested shared
  helper.
- [Risk] Tests may overfit raw ANSI sequences. -> Mitigation: test both plain
  fitting helpers and representative bottom-row output, not every escape byte.
- [Risk] Serialization could reduce spinner refresh frequency during large
  output bursts. -> Mitigation: correctness is more important than every frame;
  the next refresh will update the elapsed time.
