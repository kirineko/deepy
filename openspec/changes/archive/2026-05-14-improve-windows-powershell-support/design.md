## Context

Deepy already builds a runtime context for each agent session, including the
project root, current working directory, home directory, platform string, shell
environment, Python, Node, and selected tool availability. That context is useful
but too raw for command selection: the model sees `System:` and `Shell:` strings
without an explicit OS family, shell kind, command dialect, or path convention.

The shell tool was tightly coupled to POSIX despite the product language. It used
the model-facing tool name `bash`, described the tool as a persistent bash
session, and wrapped commands with POSIX syntax such as `$?`, `$PWD`, `printf`,
and `{ ...; } < /dev/null`. Existing utility tests covered Git Bash path
normalization and `nul` redirection rewriting, but PowerShell was not a
first-class execution target.

## Goals / Non-Goals

**Goals:**

- Make the runtime context explicitly classify the user's OS family, shell kind,
  command dialect, and preferred path style.
- Instruct the model to generate commands for the detected environment, including
  PowerShell commands on Windows PowerShell.
- Preserve existing Linux/macOS bash/zsh behavior.
- Support PowerShell command execution with cwd persistence, exit-code capture,
  timeout handling, output truncation, and structured metadata.
- Rename the model-facing tool to `shell`.
- Cover shell selection and wrapper construction with deterministic tests that do
  not require a Windows CI runner for every assertion.

**Non-Goals:**

- Add WSL, cmd.exe, or Git Bash feature parity beyond detection and conservative
  fallback behavior.
- Add a new external dependency.
- Change Deepy's config path, session storage path, or package installation
  model.
- Guarantee that Linux/macOS commands can be translated into PowerShell after the
  model has already produced the wrong command.

## Decisions

1. Rename the model-facing tool to `shell`.

   New sessions should expose the accurate `shell` tool name. The implementation
   should remove the old `bash` runtime wrapper and bash-only UI handling so the
   codebase has one current shell execution path.

2. Introduce a small runtime environment classification layer.

   The system should derive stable fields from `sys.platform`, `os.name`, `SHELL`,
   `COMSPEC`, `PSModulePath`, and available executables:

   - OS family: `windows`, `macos`, `linux`, or `unknown`
   - shell kind: `powershell`, `cmd`, `bash`, `zsh`, or `unknown`
   - command dialect: `powershell`, `cmd`, or `posix`
   - path style: `windows` or `posix`

   The runtime prompt should expose these fields in plain text rather than making
   the model infer them from long platform strings.

3. Use shell-specific wrappers behind the existing tool API.

   POSIX shells can keep the existing wrapper shape with cleanup as needed.
   PowerShell should use a wrapper that captures `$LASTEXITCODE` for native
   processes, falls back to success/failure status for PowerShell commands, emits
   a cwd marker via `Get-Location`, and exits with the captured code. This wrapper
   should be built as argv passed to PowerShell, not by asking the model to insert
   markers itself.

4. Prefer deterministic wrapper tests over Windows-only integration coverage.

   Unit tests can validate environment classification, selected executable/argv,
   marker syntax, and metadata without requiring Windows. If Windows CI is later
   available, add an integration test that runs a real PowerShell command and
   verifies cwd persistence.

5. Keep path normalization focused on tool boundaries.

   File tools should continue returning paths in the local runtime's native
   representation. The runtime context and shell metadata should tell the model
   which path style to use. Existing Git Bash conversion helpers should stay
   available, but PowerShell should not receive `/c/...` paths when native
   `C:\...` paths are appropriate.

## Risks / Trade-offs

- PowerShell exit semantics differ between native executables and cmdlets ->
  capture both `$LASTEXITCODE` and `$?`, then normalize to an integer exit code.
- Removing `bash` compatibility may make very old local histories less polished
  when rendered -> accept this trade-off to keep the current tool surface small.
- Shell detection from environment variables can be ambiguous -> expose
  conservative `unknown` values and fall back to POSIX behavior only when the
  selected shell is actually POSIX-like.
- Wrapper quoting is easy to break -> isolate wrapper construction in helpers and
  test argv strings directly.
- Windows-specific behavior may drift without Windows CI -> keep most behavior
  covered by pure unit tests and document any remaining manual validation.

## Migration Plan

1. Add runtime environment classification helpers and prompt rendering.
2. Rename the model-facing tool docs and registration from `bash` to `shell`.
3. Refactor shell command construction into POSIX and PowerShell branches.
4. Return shell kind, command dialect, and path style in shell tool metadata.
5. Add tests for classification, prompt rendering, PowerShell wrapper generation,
   POSIX regression behavior, and cwd marker extraction.
6. Run the focused prompt/tool test set locally.

Rollback is straightforward because this change is internal to prompt/tool
construction: revert to the POSIX-only shell builder and previous tool docs if the
PowerShell wrapper proves unstable.

## Open Questions

- Should Deepy allow an explicit config override for shell selection, or should it
  rely only on environment detection for now?
