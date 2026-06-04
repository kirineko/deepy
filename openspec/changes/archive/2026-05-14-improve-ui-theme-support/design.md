## Context

Deepy renders terminal UI through a small set of shared style constants in
`src/deepy/ui/styles.py`, with additional hard-coded color strings in message
and diff rendering. Those values work primarily as a dark-theme palette. In
light-background terminals, `dim`, bright-blue borders, cyan accents, and
dark-background diff previews can become low contrast or visually inconsistent.

Deepy already stores user configuration in TOML under `~/.deepy/config.toml`
and creates that file through `deepy config init`, `deepy config setup`, or the
interactive missing-key setup path. The theme choice should use the same config
path and permission guarantees instead of introducing a separate state file.

## Goals / Non-Goals

**Goals:**

- Provide readable UI palettes for light and dark terminal backgrounds.
- Keep `auto` as the saved default so Deepy can adapt when terminal background
  detection is available and otherwise use a conservative dark-compatible
  fallback.
- Prompt for theme selection the first time interactive mode starts without a
  saved UI theme.
- Persist the theme under a dedicated `[ui]` TOML section.
- Provide both non-interactive CLI configuration and an interactive slash command
  for inspecting/changing the theme.
- Centralize style selection so future UI components do not add more fixed color
  constants.

**Non-Goals:**

- Building a full theme editor or arbitrary user-defined palette format.
- Detecting every terminal emulator's background perfectly.
- Changing model behavior, session storage, or provider configuration.
- Adding new third-party dependencies.

## Decisions

1. Store the theme as `ui.theme = "auto" | "dark" | "light"`.

   This keeps UI concerns separate from model, context, logging, notify, and
   tools config. Unknown or empty values should resolve to `auto` for forward
   compatibility.

2. Introduce a theme palette object instead of more module-level color strings.

   `styles.py` should expose a small `UiTheme` value type and resolver such as
   `resolve_ui_theme(settings.ui.theme, console=console)`. UI modules should ask
   for a palette and use named roles (`muted`, `accent`, `info`, `assistant`,
   `user`, `tool`, `panel_border`, `diff_added`, `diff_removed`,
   `preview_content`) rather than hard-coded Rich style strings.

   Alternative considered: keep the current global constants and branch in each
   renderer. That is cheaper initially but spreads theme logic across the UI and
   makes later contrast fixes harder to audit.

3. Treat `auto` as best-effort detection with a stable fallback.

   If the terminal or Rich environment provides reliable background information,
   Deepy can choose light or dark. If not, `auto` should resolve to the existing
   dark-compatible palette. The welcome panel should display the resolved theme
   so users can see what was applied.

4. Ask for theme selection during first interactive startup only when missing.

   First launch means interactive mode is starting and no valid `ui.theme` is
   saved in the config file. If Deepy also needs the API key, setup should ask
   for API key/model/base URL and theme in one flow. If the API key already
   exists but the theme is missing, Deepy should ask only for theme and preserve
   the rest of the config.

5. Provide two command surfaces.

   - CLI: `deepy config theme` shows the current saved/resolved theme, and
     `deepy config theme <auto|dark|light>` updates it.
   - Interactive: `/theme` shows the current theme, and
     `/theme auto|dark|light` updates it for subsequent output and persists it.

   The CLI command supports scripting and setup documentation. The slash command
   lets users fix readability from inside the session where the problem is
   visible.

## Risks / Trade-offs

- [Risk] Some terminals do not expose reliable background color information for
  `auto`. -> Mitigation: keep explicit `light` and `dark` choices, show the
  resolved theme, and document that `auto` is best effort.
- [Risk] Changing all renderers at once can create regressions in snapshots or
  ANSI output tests. -> Mitigation: migrate through a palette API and update
  focused rendering tests for both light and dark themes.
- [Risk] Existing config files will not have `[ui]`. -> Mitigation: parsing
  defaults to `auto`, and first interactive startup prompts once and writes the
  missing setting without discarding existing config.
- [Risk] Persisting from an interactive slash command can overwrite masked or
  computed config output if implemented through `settings_to_toml_dict`.
  -> Mitigation: update config through a dedicated writer that preserves secrets
  and writes private permissions.

## Migration Plan

1. Add `UiConfig` parsing and TOML serialization with `theme = "auto"` default.
2. Add a config update helper for changing only `ui.theme` while preserving
   existing settings.
3. Introduce theme palettes and thread the active palette through welcome,
   message, terminal status, prompt, and diff renderers.
4. Extend setup/init, first interactive startup, `deepy config theme`, and
   `/theme`.
5. Add tests for config parsing/writing, first-start prompt behavior, command
   behavior, and light/dark rendering contrast-critical styles.

Rollback is straightforward: the `[ui]` section can remain harmless in config
while the UI falls back to existing dark-compatible defaults.

## Open Questions

- Whether `auto` should try terminal background detection in the first
  implementation or simply save `auto` and resolve to dark until reliable
  detection is introduced.
- Whether documentation should recommend `light` explicitly for known light
  terminal profiles or keep guidance terminal-agnostic.
