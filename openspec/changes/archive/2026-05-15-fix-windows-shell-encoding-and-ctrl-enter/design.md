## Context

Deepy already has separate POSIX, PowerShell, and cmd shell wrappers. The
PowerShell wrapper sets process-local UTF-8 output defaults and Python UTF-8
environment defaults, but shell capture currently reads subprocess output through
Python text mode as UTF-8. Windows native commands can still write UTF-16LE or
code-page bytes to redirected output, so a command such as `wsl.exe --status` can
render as mojibake even though the wrapper itself is UTF-8-aware.

Prompt input also carries historical Windows special casing. A previous change
advertised Ctrl+J for Windows because it was reliable there, while Shift+Enter
remained terminal-dependent. Follow-up testing showed Ctrl+Enter is also invalid
or inconsistent in many terminals. The desired contract is therefore simpler:
all platforms expose Ctrl+J as the only newline shortcut.

## Goals / Non-Goals

**Goals:**

- Decode shell stdout and stderr from bytes, with fallbacks that cover UTF-8,
  UTF-16-style Windows output, and GBK-compatible Windows output.
- Preserve shell cwd tracking, exit-code tracking, timeout handling, output
  truncation behavior, and the existing model-facing tool result shape.
- Avoid requiring users or the model to run `chcp`, edit PowerShell profiles, or
  prepend encoding boilerplate for ordinary shell inspection.
- Support Ctrl+J as the cross-platform prompt newline shortcut.
- Remove Shift+Enter and Ctrl+Enter newline sequence handling.
- Remove Windows-specific newline shortcut branching.

**Non-Goals:**

- Do not change the shell tool function schema or session storage format.
- Do not mutate the user's terminal or shell configuration globally.
- Do not add a charset detection dependency.
- Do not make plain Enter insert newlines.
- Do not keep Shift+Enter or Ctrl+Enter as user-facing newline shortcuts or
  toolbar hints.

## Decisions

1. Capture shell output as bytes and decode after process exit.

   Shell subprocesses should write stdout and stderr into binary temporary files.
   After wait or timeout handling, Deepy decodes captured bytes through a small
   helper before sentinel extraction and output truncation. This keeps the
   existing shell execution flow intact while moving the fragile part from
   implicit text-mode decoding to explicit compatibility decoding.

   Alternative considered: keep text-mode capture and set more PowerShell
   encoding variables. That still does not control every native Windows command
   and cannot recover output already written in another byte encoding.

2. Use deterministic standard-library decode fallbacks.

   The decode helper should prefer UTF-8/UTF-8-SIG, detect likely UTF-16 output
   using BOM or NUL-byte distribution, then try GB18030, and finally fall back to
   UTF-8 with replacement. GB18030 covers common GBK/CP936 Chinese output without
   a new dependency. The helper can return the selected encoding for metadata,
   but readable output is the primary contract.

   Alternative considered: use locale preferred encoding. That makes behavior
   depend on the machine running Deepy and is less predictable in tests.

3. Keep sentinel parsing on decoded text.

   The PowerShell/POSIX/cmd wrappers already append ASCII cwd and exit-code
   sentinel lines. After decoding, existing sentinel extraction can continue to
   operate on text. Tests should cover that visible output decoding does not
   break cwd or exit-code metadata.

   Alternative considered: parse sentinel bytes before decoding. That adds
   complexity because stdout could be encoded differently by the command and the
   wrapper. The current wrapper sentinel remains ASCII-compatible in normal
   decoded streams, so text parsing is simpler and sufficient.

4. Treat Ctrl+J as the only newline shortcut.

   Prompt input should bind bare Ctrl+J to newline insertion on all platforms.
   Shift+Enter and Ctrl+Enter should not be patched through terminal escape
   sequences or advertised in toolbar text. This favors one reliable control
   character over terminal-specific modified-Enter protocols.

   Alternative considered: use Ctrl+Enter globally. Rejected after user testing
   showed it is invalid in many terminals.

5. Collapse platform-specific toolbar text.

   The prompt help should be identical across platforms: Enter submits, while
   Ctrl+J inserts newlines. This simplifies the UI and removes the Windows-only
   branch plus the terminal-specific Shift/Ctrl+Enter sequence overrides.

## Risks / Trade-offs

- Some Windows commands may emit an encoding outside UTF-8, UTF-16, or GB18030 ->
  fall back with replacement and expose enough metadata for debugging.
- UTF-16 detection can misclassify arbitrary binary-like output -> this only
  affects shell text display; binary file handling remains in file tools.
- Users may expect Shift+Enter or Ctrl+Enter from other tools -> toolbar and docs
  will consistently point to Ctrl+J as the single multiline shortcut.

## Migration Plan

No user migration is required. Existing sessions, config files, and tool schemas
remain compatible. Rollback is reverting the implementation; no persisted data is
rewritten by this change.
