## 1. Theme, Footer, And Copy

- [x] 1.1 Change the shared light theme mapping to `solarized-light`.
- [x] 1.2 Simplify prompt action hints to show only `Esc interrupt`.
- [x] 1.3 Preserve terminal-native transcript text selection/copy affordances.

## 2. Bottom Interaction Sheet

- [x] 2.1 Add a bottom interaction sheet host above the prompt panel.
- [x] 2.2 Move inline choice flows to the bottom sheet and remove transcript decision-result mutation.
- [x] 2.3 Update theme/model/session choice tests to assert no transcript pollution.

## 3. Management Surfaces

- [x] 3.1 Redesign skill management with visible tabs, compact one-line rows, and state classes.
- [x] 3.2 Reformat status/config information into concise grouped summaries.
- [x] 3.3 Update focused tests for skill and status/config UX.
- [x] 3.4 Keep skill management install/uninstall actions inside the management flow without transcript output.
- [x] 3.5 Align reasoning/thinking transcript styling with compact transcript rows.
- [x] 3.6 Load and refresh skill market data asynchronously with visible loading states.
- [x] 3.7 Widen skill rows to use available modal width while keeping single-line truncation.
- [x] 3.8 Align Modern UI `/mcp` with Classic UI by printing current MCP tools to the transcript.
- [x] 3.9 Render user local command (`!`) results visibly in the Modern UI transcript.

## 4. Validation

- [x] 4.1 Persist `ui.interface` and route default `deepy` startup through Classic/Modern UI config.
- [x] 4.2 Add `/ui` in Classic UI and Modern UI.
- [x] 4.3 Update setup/reset UI selection to Classic/Modern plus dark/light combinations.
- [x] 4.4 Update UI naming from stable/experimental to Classic/Modern.
- [x] 4.5 Validate the OpenSpec change in strict mode.
- [x] 4.6 Run focused TUI tests and quality checks.
