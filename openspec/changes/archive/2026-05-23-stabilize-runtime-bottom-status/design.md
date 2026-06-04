## Context

The stable UI renders active model work and local command execution with a transient one-line status at the terminal bottom. The current implementation builds a single Rich `Text`, strips it to `status.plain`, fits that whole string, and writes it directly into the final terminal row.

That approach has two weak points. First, runtime-critical content such as spinner, elapsed time, and interrupt affordance competes with unbounded command or tool-argument text. Second, payload text can contain newlines, carriage returns, tabs, ANSI escape sequences, or other control characters that do not behave like printable cells when written into a terminal row.

## Goals / Non-Goals

**Goals:**

- Keep the transient bottom status to one terminal row during active work.
- Preserve the runtime prefix (`spinner`, elapsed time, interrupt hint) whenever terminal width allows.
- Keep command text visible for local commands and shell tool calls.
- Tail-truncate command payloads so the command prefix remains intact.
- Sanitize runtime payload text before fitting and writing it to the terminal.
- Keep the implementation local to terminal UI formatting and status rendering.

**Non-Goals:**

- Reintroducing a persistent fixed footer or a second terminal-bottom row.
- Changing command execution, tool protocol payloads, session persistence, or provider behavior.
- Hiding command text as the primary mitigation.
- Redesigning the experimental Textual TUI.

## Decisions

### Segment runtime status before fitting

Runtime status should be represented as prioritized display segments before converting to the final string:

```text
[protected prefix] + [activity label] + [payload]
```

The protected prefix contains spinner, elapsed time, and interrupt affordance. The activity label contains concise state such as `thinking`, `tool [Shell]`, or `local command`. The payload contains command or tool parameter detail.

This keeps priority explicit. Fitting the final row can reduce payload first, then label if necessary, and only reduce the prefix in extremely narrow terminals.

Alternative considered: keep fitting the whole status string. That is simpler but cannot encode which parts are allowed to lose width first.

### Sanitize payload text before width calculation

Runtime status payloads should be normalized to a printable single-line form before display-cell fitting. Newlines, carriage returns, tabs, ANSI escape sequences, and non-printing control characters should not be written through to the bottom row.

Alternative considered: rely on Rich `Text.plain` and `cell_len`. That strips Rich styling but does not make arbitrary command text terminal-safe.

### Tail-truncate commands

Local command and shell command payloads should preserve the left side of the command and omit only the tail when space runs out.

This is intentional because the command prefix usually carries the action and execution entrypoint: `uv run`, `git commit`, `openspec validate`, `python -m`, and similar prefixes are often more important than the final argument. The command must not disappear entirely when normal terminal width leaves enough room for a payload.

Alternative considered: middle truncation. That can preserve target paths, but it hides part of the command prefix and is less suitable for a runtime execution indicator.

### Keep tool summaries concise at the status boundary

Final transcript rendering can keep richer summaries, but runtime status should display concise, bounded tool progress. For shell calls, this means label plus bounded command. For non-shell tools, this means label plus bounded payload snippet if useful.

Alternative considered: shorten all tool parameter summaries at `message_view.py`. That risks reducing detail in normal transcript output, so runtime status should apply its own fitting policy unless shared helpers can do so without changing transcript behavior.

## Risks / Trade-offs

- Payload sanitization may make a complex command look slightly different from its raw typed form -> use whitespace-preserving normalization where possible and only replace control behavior that can corrupt the bottom row.
- Tail truncation can hide important target paths at the end of very long commands -> preserve transcript/status-line completion output elsewhere and keep enough payload width for normal commands.
- Segment fitting adds more formatting logic -> keep helpers small and test them with display-cell assertions.
- Terminal width can change while a run is active -> keep recalculating width on each status update as the current bottom-status writer already does.
