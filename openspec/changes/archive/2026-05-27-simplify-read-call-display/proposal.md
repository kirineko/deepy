# Simplify Read Call Display

## Why

`Read` calls that pass multiple paths currently expose raw JSON arguments in the
terminal transcript, including keys, list brackets, and absolute paths. This
makes common multi-file reads noisy and harder to scan.

## What Changes

- Render `Read` call parameters as concise path text.
- For multiple read targets, show the target paths directly instead of raw JSON.
- Shorten absolute paths under the project root to project-relative paths.

## Impact

- Affects stable terminal and TUI transcript rendering through shared tool
  message formatting.
- No tool execution or storage behavior changes.
