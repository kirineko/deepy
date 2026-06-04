## 1. Shared Slash Command Ranking

- [x] 1.1 Add a shared ranking API for slash command candidates that supports bare discovery and typed search.
- [x] 1.2 Define intent-oriented priorities for common workflow commands, subagents, skills, and lower-frequency management commands.
- [x] 1.3 Rank exact matches before prefix matches, prefix matches before weaker matches, then use shared priority and alphabetical tie-breakers.
- [x] 1.4 Preserve existing command identity, skill lookup, subagent lookup, and `/skill:<name>` compatibility semantics.

## 2. Stable Prompt-Toolkit UI

- [x] 2.1 Replace label-only slash `WordCompleter` usage with a slash-aware completer that consumes the shared ranking API.
- [x] 2.2 Render completion metadata for descriptions and loaded skill markers while preserving existing command insertion behavior.
- [x] 2.3 Keep file mention completion merged with prompt completion without cross-interference between `/` and `@` tokens.

## 3. Experimental Textual TUI

- [x] 3.1 Update prompt-adjacent slash suggestions to use the shared ranking API.
- [x] 3.2 Remove source-level truncation that limits Textual slash suggestions to the first eight candidates while keeping the visual max-height behavior.
- [x] 3.3 Ensure bare `/` suggestions expose built-in commands, subagents, and skills through keyboard navigation.
- [x] 3.4 Align Textual command discovery ordering with the same intent-oriented priority where that surface lists Deepy commands.

## 4. Tests

- [x] 4.1 Update `tests/test_slash_commands.py` to cover bare `/` ordering, `/re` ordering, `/skil` ordering, subagent visibility, and loaded skill priority.
- [x] 4.2 Add or update stable prompt completer tests for labels, descriptions, loaded skill markers, and file mention non-interference.
- [x] 4.3 Update `tests/test_tui_app.py` to prove bare `/` exposes subagents and skills beyond the visible row limit and remains keyboard-selectable.
- [x] 4.4 Add Textual TUI tests for typed slash ranking and command insertion without prompt submission.

## 5. Validation

- [x] 5.1 Run focused slash command, stable prompt input, and Textual TUI tests.
- [x] 5.2 Run `openspec validate improve-slash-command-discovery-ranking --type change --strict`.
- [x] 5.3 Run the repo's standard lightweight checks required for this UI-scoped change.
