## Context

Deepy's interactive loop currently routes prompt text to three paths: empty
input is ignored, `/` input is handled as an in-process slash command, and all
other text is sent through `_run_once_with_status()` to the model. The model can
already invoke a `shell` tool, but that path is model-mediated and uses
`subprocess` with captured stdout/stderr and no TTY.

The new `!` command mode is a fourth interactive path. It is user-directed,
bypasses the model, and should feel closer to a terminal command than a model
tool call. At the same time, Deepy must persist the command and result so the
next model turn can use that local evidence as context.

## Goals / Non-Goals

**Goals:**

- Route prompts whose trimmed text starts with `!` to a local command runner
  instead of the model.
- Execute the command in the detected user shell: zsh/bash on POSIX-like
  systems and PowerShell/cmd on Windows.
- Provide a TTY/PTY execution environment, including Windows support through
  `pywinpty`.
- Render local command output and exit status in the interactive terminal.
- Persist a synthetic shell tool transcript so future model turns replay the
  command and output as context.
- Keep display output and stored context output truncation separate.
- Treat command-mode execution as non-interactive-command-first.

**Non-Goals:**

- Supporting `cd` or other command-mode working-directory mutation.
- Sharing command-mode cwd state with model tool runtime cwd.
- Making full-screen interactive programs such as editors, pagers, or SSH a
  first-version supported workflow.
- Sending `!` commands to the model for interpretation or approval.
- Recording API token usage for local-only command execution.

## Decisions

1. Add a `!` branch in the interactive prompt loop before model execution.

   After input is read and blank/control input is handled, Deepy should detect
   `text.strip().startswith("!")`. A non-empty command after the bang bypasses
   slash parsing and `_run_once_with_status()`. Empty `!` input should show a
   concise usage message and should not create a model turn.

   Alternative considered: implement `!` as a slash command. Rejected because
   the desired UX is shell-style command entry, not a command namespace.

2. Use a dedicated local command runner instead of `ToolRuntime.shell()`.

   The existing shell tool is designed for model function calls and uses
   non-TTY subprocess capture. Local command mode needs PTY behavior, terminal
   rendering, and a separate context-storage truncation policy. The runner can
   reuse shell detection and command wrapping concepts where appropriate, but
   should expose command-mode-specific result metadata.

   Alternative considered: call `ToolRuntime.shell()` directly. Rejected because
   it does not simulate a TTY and would make later TTY behavior harder to add
   cleanly.

3. Provide PTY on POSIX and `pywinpty` on Windows.

   POSIX-like platforms should use Python's standard `pty`/`os.openpty()`
   primitives with the selected runtime shell. Windows should use `pywinpty` so
   commands that check for a terminal can run in a ConPTY-backed environment.
   If the Windows PTY dependency is unavailable at runtime, the command should
   fail with a clear setup error rather than silently degrading to a non-TTY
   path.

   Alternative considered: Windows subprocess fallback. Rejected after user
   confirmation that adding `pywinpty` is acceptable and Windows TTY support is
   desired.

4. Do not support command-mode cwd mutation.

   Every `!` command should run from Deepy's active project root. Commands such
   as `!cd subdir` may execute in the child shell but must not mutate the next
   command-mode cwd, the model tool runtime cwd, or the session root.

   Alternative considered: track cwd by shell sentinels like the model shell
   tool does. Rejected because the user explicitly does not want `cd` support
   for this mode.

5. Persist command mode as a synthetic shell tool transcript.

   After local execution, Deepy should append session items that are compatible
   with replay:

   - user item: the literal `!<command>` input
   - assistant item: empty assistant content with a synthetic `shell` function
     tool call containing the command
   - tool item: `shell` result JSON with ok/error, output, exit status, cwd,
     shell kind, tty mode, and truncation metadata

   This transcript is explicitly local-synthesized, not model-generated, but it
   lets later model requests see the same evidence shape as ordinary shell tool
   output.

   Alternative considered: store a plain assistant text summary. Rejected
   because it would not reuse the existing shell output rendering or replay
   semantics.

6. Separate terminal-display output from context-stored output.

   The command runner should capture enough output to render a useful terminal
   result. Before writing the synthetic tool result to the session, Deepy should
   apply a stricter context storage limit and include metadata showing whether
   stored output was truncated. The terminal panel may show more than the
   stored context payload, but both should be bounded.

   Alternative considered: store the full displayed output. Rejected because a
   single local command can otherwise pollute the next model context.

7. Treat non-interactive commands as the supported first-version target.

   The runner should support commands like tests, builds, `ls`, `python -c`,
   and package-manager scripts. It should provide timeout/interruption handling
   for long-running commands, but full bidirectional interaction with programs
   that require ongoing user input is not a first-version requirement.

   Alternative considered: build a full terminal emulator passthrough. Rejected
   because it is a larger interaction model and would need a separate UI design.

## Risks / Trade-offs

- `pywinpty` packaging can fail on some Python/Windows combinations -> Keep the
  dependency explicit and add a clear runtime error that names the missing TTY
  dependency.
- PTY output includes terminal control sequences -> Preserve enough fidelity for
  terminal-like rendering, but consider sanitizing or bounding recorded context
  output to avoid harmful or unreadable transcript content.
- Synthetic tool transcripts may diverge from SDK-generated tool calls -> Add
  replay tests that prove `DeepyJsonlSession.get_items()` returns the synthetic
  items and later model input includes them.
- Local commands can run indefinitely -> Add timeout/interruption behavior and
  record interrupted metadata.
- Stored output truncation may hide details the model needs -> Keep visible
  terminal output longer, store a clear truncation marker, and let users rerun a
  narrower command if needed.
- Bypassing the model bypasses safety/planning guidance -> Limit this to
  explicit `!` input where the user is intentionally issuing a local command.
