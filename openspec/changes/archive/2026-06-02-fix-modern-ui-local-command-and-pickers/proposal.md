# Proposal

## Why

Modern UI has two regressions in compact command flows:

- successful `!cmd` local commands render a noisy `exit 0` metadata line;
- bottom-sheet pickers such as `/model` can show only the title while their
  options are effectively invisible under the active Textual theme.

Both issues are user-visible and make common command-mode interactions harder
to scan or complete.

## What Changes

- Hide successful local command exit-code metadata in Modern UI while retaining
  non-zero exit codes and environment metadata.
- Give bottom-sheet `OptionList` controls explicit foreground, highlight,
  disabled, hover, and border styles so provider/model/theme/question options
  remain readable across Textual themes.
- Add focused regression tests for local command metadata and inline picker
  option visibility.

## Impact

- Affects only Modern UI rendering and interaction styling.
- Session persistence and command execution semantics are unchanged.
