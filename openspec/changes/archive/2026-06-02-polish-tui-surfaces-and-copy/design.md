## Context

The Classic UI and Modern UI are peer system UIs. Classic UI is the
Rich/prompt-toolkit terminal UI, and Modern UI is the Textual terminal UI. Modern
UI uses richer transcript blocks and several inline or modal surfaces. Some
surfaces still work against the desired flow: theme/model/session choices are
mounted into the transcript, the selection result mutates transcript content,
skill market tabs are only described in help text, and status/config information
is formatted as broad markdown. The prompt footer also advertises both `Esc` and
`Ctrl+C` interruption, which creates visual noise.

## Goals / Non-Goals

**Goals:**

- Keep the transcript focused on user/assistant/tool output.
- Use a bottom sheet for transient choices that are part of the current input flow.
- Make management screens denser, clearer, and visually differentiated.
- Improve copy affordances without adding a custom clipboard subsystem.
- Persist the default UI choice and route the default `deepy` command through it.
- Keep `deepy tui` as a compatibility command for directly starting Modern UI.

**Non-Goals:**

- Remove existing keyboard shortcuts that already work.
- Replace all management screens with a new framework.
- Implement mouse-driven full text selection if Textual/terminal support is unavailable.
- Remove or deprecate Classic UI.

## Decisions

- Use `solarized-light` as the default Textual theme for shared `light`, while keeping explicit Textual theme overrides unchanged.
- Do not intercept `Ctrl+C`/`Cmd+C` at the app level. Run Textual without terminal
  mouse reporting so the terminal can provide native text selection and clipboard
  copy behavior.
- Add a dedicated bottom `InteractionSheet` host mounted above the prompt. Inline choices use this host and unmount after completion or cancellation.
- Keep audit/question/model/theme/session choice results out of the transcript. Completion updates status or continues workflow instead.
- Keep skill management as a modal screen, but add visible tabs, one-line rows, and CSS classes for installed/market/built-in/updateable entries.
- Reformat status/config markdown into grouped sections with short key-value summaries.
- Store the default UI in `ui.interface` with `classic` as the default for missing
  config. Use `modern` for the Textual UI.
- Add `/ui` in both Classic UI and Modern UI. It persists the default UI for the
  next startup; it does not hot-swap the running UI.
- Change setup/reset UI selection to four combinations: Classic dark, Classic
  light, Modern dark, Modern light.

## Risks / Trade-offs

- Bottom-sheet choices are a new layout surface and can overlap the prompt if sizing is wrong. Mitigation: cap height and keep it above the prompt panel.
- Some terminals may still limit copy behavior despite Textual selection affordances. Mitigation: enable the supported Textual selection path and avoid custom clipboard behavior.
- Skill market rows may truncate long descriptions. Mitigation: one-line truncation is intentional and detail remains available through the existing view action.
