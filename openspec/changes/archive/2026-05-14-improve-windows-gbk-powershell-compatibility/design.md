## Context

Deepy already classifies runtime shell environments and has separate shell wrappers for POSIX, PowerShell, and cmd. It also preserves CRLF and UTF-16LE file encodings and installs a small prompt-toolkit ANSI override for Shift+Enter.

The Windows compatibility gap is narrower than generic Windows support: the reported environment is Windows Terminal running PowerShell 7. In that environment, Python child processes can still inherit Windows ANSI/GBK-oriented defaults, text files may be encoded as GBK-compatible byte streams, and prompt-toolkit can receive Windows console input records instead of the vt100 sequences currently patched by Deepy.

## Goals / Non-Goals

**Goals:**

- Make Windows Terminal + PowerShell 7 shell execution safe for Python programs containing non-ANSI Unicode text.
- Allow `read` and `modify` to round-trip GBK-compatible text files without replacement-character corruption.
- Make Shift+Enter insert a newline in the Windows console input path while preserving Enter-submit behavior.
- Keep macOS/Linux shell execution, POSIX command construction, and prompt behavior unchanged.
- Preserve existing read-before-write, stale-write, CRLF, UTF-8, and UTF-16LE guarantees.

**Non-Goals:**

- Do not convert every file to UTF-8.
- Do not change user shell configuration globally, run `chcp`, or mutate terminal settings outside the child process.
- Do not add a charset detection dependency.
- Do not redesign prompt input behavior or change the Enter-to-submit contract.
- Do not make broad cmd.exe behavior changes beyond regression-safe shared helpers.

## Decisions

1. Gate Windows shell encoding setup by runtime environment.

   For shell invocations whose detected OS family is `windows`, inject a child-process environment that sets `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` when the user has not already provided values. For PowerShell wrappers, also set process-local output encoding at the top of the generated script.

   Rationale: this fixes Python source/output encoding failures without touching POSIX shells or user-level PowerShell profiles. It is safer than asking the model to prepend encoding boilerplate to every generated Python script.

   Alternatives considered:

   - Tell the model to avoid Unicode in generated Python. Rejected because it is unreliable and constrains normal coding.
   - Run `chcp 65001`. Rejected because it mutates console state and is cmd-oriented, not a good fit for PowerShell 7.
   - Apply UTF-8 variables on all platforms. Rejected because macOS/Linux already work and the change should be Windows-scoped.

2. Extend text encoding support with strict decode fallback.

   Keep BOM-based UTF-16LE detection first. Then try UTF-8/UTF-8-SIG using strict decoding. If strict UTF-8 fails, try `gb18030` strict decoding and record that encoding for write-back. Continue writing with the detected encoding.

   Rationale: GB18030 is a superset that covers common GBK/CP936 files while using the Python standard library. Strict UTF-8 first ensures valid UTF-8 files remain classified as UTF-8 on macOS/Linux and Windows.

   Alternatives considered:

   - Decode with locale preferred encoding. Rejected because it makes behavior depend on the machine running Deepy and could affect macOS/Linux.
   - Use charset-normalizer or chardet. Rejected because the change does not need a new dependency for the reported failure.
   - Always write modified files as UTF-8. Rejected because it would surprise Windows users and break the existing preserve-encoding pattern.

3. Add a Windows-only prompt-toolkit input compatibility patch.

   Keep the existing ANSI sequence override. In addition, when running on Windows and prompt-toolkit's Win32 console input path is available, patch Shift+Enter console records to emit the same key sequence Deepy already binds for newline insertion: Escape followed by Enter.

   Rationale: Windows Terminal may deliver console input records rather than the vt100 sequences currently covered. Reusing the existing Escape+Enter binding keeps the rest of the prompt code unchanged.

   Alternatives considered:

   - Make plain Enter insert newlines and require another shortcut to submit. Rejected because it changes the core prompt contract.
   - Add a new user setting for multiline mode. Rejected because this is a compatibility bug, not a preference.
   - Patch prompt-toolkit globally without platform guards. Rejected because it could affect macOS/Linux and non-Windows terminals.

4. Test by construction rather than relying on a live Windows host.

   Unit tests should exercise helper functions and monkeypatched prompt-toolkit code paths with simulated Windows runtime inputs. Manual Windows Terminal verification remains valuable, but the required regression coverage should be runnable on macOS/Linux CI.

## Risks / Trade-offs

- [Risk] PowerShell output encoding assignment may fail in unusual hosts. -> Keep the script snippet process-local and simple, and preserve structured shell failure behavior if the shell itself errors.
- [Risk] Some legacy byte files may be neither UTF-8 nor GB18030. -> Keep replacement-error fallback only after strict known encodings fail, and report metadata so failures are visible.
- [Risk] GB18030 can decode a wide byte range, so some non-text binary files might appear textual. -> Existing binary/image/PDF special cases remain first; this change does not add binary detection.
- [Risk] prompt-toolkit internals can change. -> Keep the Win32 patch isolated, idempotent, guarded by import availability, and covered by tests.
- [Risk] macOS/Linux regressions from shared helpers. -> Add tests that POSIX shell invocations do not receive Windows-specific encoding setup and existing Shift+Enter vt100 behavior remains unchanged.
