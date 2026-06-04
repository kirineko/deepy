## Context

The first Windows compatibility release fixed Python Unicode shell execution. The second release improved CRLF matching and added Ctrl+J as a Windows newline fallback. User testing now gives two clearer signals:

- Ctrl+J works on Windows Terminal + PowerShell 7, while Shift+Enter remains unreliable. The Windows UI should stop advertising or trying to implement Shift+Enter as the Windows multiline key.
- `modify` still fails in realistic edit sessions. The logged `two_sum.py` workflow showed repeated failed matches, increasing blank lines, deletion of the target file, failed managed recreation due to stale read state, and a final shell here-string write whose Chinese text displayed as mojibake in PowerShell `cat`.

The likely write-side defect is that Deepy normalizes content to CRLF and then writes through Python text mode. On Windows, text-mode newline translation can turn existing `\n` into `\r\n`; if the string already contains `\r\n`, that can become `\r\r\n`, creating apparent blank lines and destabilizing later exact matches.

## Goals / Non-Goals

**Goals:**

- Use Ctrl+J as the supported Windows Terminal multiline newline key.
- Remove Windows-specific Shift+Enter monkeypatching and Windows Shift+Enter UI promises.
- Keep existing POSIX/modern-terminal escape-sequence handling for Shift+Enter where it already works.
- Write managed text files using explicit encoded bytes so Deepy, not the platform text layer, controls line endings.
- Preserve detected encoding when editing existing files, including UTF-8, UTF-8 with signature, UTF-16LE, and GBK-compatible encodings.
- Use UTF-8 with signature for newly created Windows non-ASCII text files so Windows Notepad and common IDEs recognize them as UTF-8.
- Improve model-facing tool guidance so repeated `old_string not found` failures lead to a managed full-file replacement path, not shell deletion and here-string recreation.

**Non-Goals:**

- Do not support Shift+Enter on Windows Terminal if user testing shows it is unreliable.
- Do not guarantee correct rendering through `cat` in a GBK-configured PowerShell session.
- Do not change the model-facing tool function signatures.
- Do not weaken stale-write protection for existing files.
- Do not force UTF-8 with signature for every file on every platform.

## Decisions

1. Make Ctrl+J the Windows multiline key.

   Windows user testing showed Ctrl+J works and Shift+Enter does not. The practical product decision is to optimize the UI around the reliable input path. Windows-specific Shift+Enter monkeypatches add maintenance risk without working for the target environment, so they should be removed.

   Alternative considered: keep trying deeper prompt-toolkit/Win32 hooks. This has already failed user validation and increases risk around keyboard input internals.

2. Preserve Shift+Enter escape-sequence support only for terminals that already expose it.

   The existing ANSI sequence overrides are useful for POSIX and modern terminal environments where Shift+Enter produces a distinguishable sequence. Keeping that path preserves current non-Windows behavior while avoiding a Windows-specific promise.

   Alternative considered: remove all Shift+Enter support globally. That would be an unnecessary regression for terminals where it already works.

3. Replace text-mode writes with byte writes.

   `_write_text_with_encoding()` should encode content with the selected codec and call `write_bytes()`. This prevents Windows newline translation from changing already-normalized CRLF content and keeps write behavior consistent across macOS, Linux, and Windows.

   Alternative considered: call `Path.write_text(..., newline="")`. Explicit byte writes are simpler to reason about and make encoding behavior obvious.

4. Use `utf8-sig` for new Windows non-ASCII text files.

   `utf8` and `utf8-sig` both encode the same Unicode content as UTF-8. The difference is the three-byte BOM/signature at the start of the file. On Windows, that signature is still useful as an explicit "this file is UTF-8" marker for Notepad, older tools, and code paths that might otherwise guess ANSI/GBK. Python 3 accepts UTF-8 BOM source files, and common IDEs handle them correctly.

   This is not meant to make GBK PowerShell `cat` display UTF-8 correctly. It is meant to make the file's encoding self-identifying for Windows editors.

   Alternative considered: use plain UTF-8 everywhere. That is cleaner on Unix-like systems and remains the default there, but it leaves Windows editor detection more dependent on heuristics.

5. Treat shell recreation after `modify` failure as an anti-pattern.

   If an agent deletes a read file and then tries `modify(content=...)`, stale protection correctly rejects the operation because the file has changed outside the managed write path. Tool guidance should steer the model toward managed full-file replacement before deletion, and error guidance should tell it to re-read or use the managed replacement path rather than writing Unicode here-strings through PowerShell.

   Alternative considered: allow `modify(content=...)` to recreate a deleted file if the snapshot says it used to exist. That weakens stale-write safety and can silently overwrite user changes.

## Risks / Trade-offs

- UTF-8 with signature may be less preferred in some Unix workflows -> Apply it only to new Windows non-ASCII text files; preserve existing file encodings on edit.
- Removing Windows Shift+Enter support may disappoint users who expect that shortcut -> The UI will clearly advertise Ctrl+J on Windows, which is validated as working.
- Byte writes change a low-level write primitive -> Add tests proving LF/CRLF bytes remain exact and existing encoding preservation still passes.
- Stronger tool guidance cannot force model behavior completely -> Add tests for tool behavior where possible and update docs to bias the model away from shell here-string writes.

## Migration Plan

No user migration is required. Existing files keep their detected encodings when edited. New Windows non-ASCII files created through Deepy's managed tools may be written as UTF-8 with signature so Windows editors identify them reliably. Rollback is reverting the implementation commit; no persistent Deepy state format changes are introduced.
