## Why

The skill market menu recently added a second full-screen picker for choosing
whether to install a selected market skill into the user or project directory.
That interaction is correct, but it exposed a regression in the existing skill
view action: viewing a skill can fall back to Deepy's main output or fail when
the selected market item is not installed.

## What Changes

- Restore normal skill view behavior from the skill menu for installed user,
  project, and market-managed skills.
- Show skill details in a dedicated full-screen view window instead of printing
  the skill body into Deepy's main conversation/output area.
- Keep the install scope picker behavior unchanged.
- Make market-list view behavior explicit: viewing an installed market item
  opens the installed skill details; viewing an uninstalled market item shows
  market metadata in the same dedicated view window rather than reporting that
  the skill is not installed.
- Preserve current update, uninstall, remove-local, refresh, and tab-switch
  menu behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `terminal-ui`: revise `/skills` menu behavior so skill view actions render in
  a dedicated full-screen viewer and work correctly after the install scope
  picker change.

## Impact

- Affected code: `src/deepy/ui/skill_picker.py` and
  `src/deepy/ui/terminal.py`.
- Affected tests: `tests/test_skill_picker.py` and
  `tests/test_terminal_ui.py`.
- Affected specs: `openspec/specs/terminal-ui/spec.md`.
- No CLI command syntax, market API, or install record format changes are
  expected.
