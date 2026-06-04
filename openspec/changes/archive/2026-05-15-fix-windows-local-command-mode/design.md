## Context

Deepy 0.1.12 added local command mode so users can type `!cmd` in the
interactive prompt and execute a command without sending it to the model. The
current implementation uses POSIX PTY support on macOS/Linux and `pywinpty` on
Windows.

Windows release validation found two practical failures after running commands
such as `!wsl --version`:

- the shell output panel can become misaligned;
- the next prompt can receive raw terminal control sequences as text, making
  normal typing unusable until the process is restarted.

The feature does not need full terminal emulation on Windows to meet its main
purpose. Users primarily need a reliable way to run known non-interactive
commands and include their output in the conversation context.

## Goals / Non-Goals

**Goals:**

- Make Windows local command mode stable after each `!` command.
- Remove `pywinpty` from the dependency graph.
- Execute Windows local commands with a non-interactive subprocess runner.
- Capture stdout and stderr, normalize line endings, sanitize terminal control
  sequences, and render/persist readable text.
- Preserve existing `!cmd` UX and synthetic shell transcript persistence.
- Keep macOS/Linux behavior stable.

**Non-Goals:**

- Support interactive TUI programs in Windows local command mode.
- Persist `cd` or other process-local environment changes across commands.
- Provide a general terminal emulator inside Deepy.
- Change model-driven shell tool execution semantics.

## Decisions

### Use subprocess pipes on Windows

Windows local command mode will use `subprocess.Popen` or equivalent with
`stdin=DEVNULL`, stdout/stderr captured, and shell arguments selected from the
detected shell dialect.

Rationale: pipes do not allocate or mutate a pseudo-terminal, so they avoid the
console-mode and prompt corruption risks seen with `pywinpty`.

Alternatives considered:

- Keep `pywinpty` and restore console state after each command. This preserves
  more TTY behavior but keeps a difficult cross-terminal failure mode in the
  critical interactive path.
- Use plain `shell=True`. This is simpler but weakens existing shell dialect
  control and makes quoting behavior harder to reason about.

### Treat Windows command mode as intentionally non-interactive

Windows `!cmd` execution will not accept stdin and will time out long-running
commands according to the configured timeout. Commands that require prompts,
password entry, editors, pagers, or full-screen UI are out of scope.

Rationale: the feature is a direct command shortcut, not an embedded terminal.
This explicit boundary is easier for users to understand and easier to test.

### Sanitize captured output before display and context persistence

The Windows runner will decode captured bytes with the same compatibility path
as the model shell tool before any display or context truncation. It will
recognize UTF-8, UTF-16, UTF-16LE-shaped output, and GB18030-compatible legacy
Windows output, then normalize `\r\n` and bare `\r` to `\n`, remove ANSI/VT
escape sequences and non-printable terminal control characters, and keep normal
Unicode text such as Chinese output.

Rationale: raw terminal control sequences break Rich panel measurement and can
pollute subsequent prompt input or session history. Legacy Windows encodings can
also corrupt both terminal display and the synthetic shell result if decoded as
UTF-8 with replacement.

### Preserve synthetic shell transcript shape

The stored session records remain:

1. user item with the literal `!cmd`;
2. synthetic `function_call` item named `shell`;
3. matching `function_call_output` item with shell result JSON.

Rationale: later model turns already depend on the Agents SDK-compatible replay
shape. The execution backend should change without changing the context
contract.

## Risks / Trade-offs

- Windows users lose support for interactive TTY commands through `!cmd` →
  Document that Windows local command mode is non-interactive and prefer
  ordinary terminal usage for interactive commands.
- stdout/stderr ordering may differ when captured separately → Use a deliberate
  merge strategy and test the displayed output shape; preserving exact terminal
  interleaving is not required for this mode.
- Over-aggressive sanitization could remove useful formatting → Strip terminal
  control sequences but preserve printable Unicode and normal whitespace.
- Some commands may behave differently without a TTY → This is acceptable for
  Windows local command mode; users can still run interactive commands directly
  in their terminal outside Deepy.

## Migration Plan

- Remove `pywinpty` from dependencies and lockfile.
- Implement the Windows pipe runner behind the existing `run_local_command`
  interface.
- Add regression tests for Windows command execution, timeout, output
  sanitization, session persistence, and absence of the `pywinpty` dependency.
- Verify with the existing full test suite.

Rollback is straightforward: revert the change and restore the previous
`pywinpty` dependency, though that would reintroduce the prompt corruption risk.
