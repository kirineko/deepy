## 1. Configuration Model And Persistence

- [x] 1.1 Add `UiConfig` with validated `theme` values `auto`, `dark`, and `light`.
- [x] 1.2 Include `[ui] theme = "auto"` in config serialization and generated config files.
- [x] 1.3 Add a helper that updates only `ui.theme` while preserving existing TOML config values and `0600` permissions.
- [x] 1.4 Add config parsing tests for missing, valid, and invalid `ui.theme` values.
- [x] 1.5 Add config writing tests for `config init`, `config setup`, and targeted theme updates.

## 2. Theme Palette Foundation

- [x] 2.1 Replace fixed shared style constants with a theme palette API that exposes named UI roles.
- [x] 2.2 Define dark and light palettes for text, muted text, accents, assistant/user/system/tool panels, status, errors, and borders.
- [x] 2.3 Define diff and write-preview styles for both light and dark palettes with readable foreground/background contrast.
- [x] 2.4 Add `auto` resolution with documented fallback behavior when terminal background detection is unavailable.
- [x] 2.5 Add focused unit tests for theme validation, palette role availability, and `auto` resolution fallback.

## 3. UI Renderer Migration

- [x] 3.1 Thread the active palette into welcome panel rendering and show the active UI theme in startup settings.
- [x] 3.2 Update message panel, Markdown, tool-call, tool-output, and generic history rendering to use palette roles.
- [x] 3.3 Update diff and write-preview renderers to use theme-specific contrast styles.
- [x] 3.4 Update prompt/user input rendering, thinking/progress summaries, status lines, resume messages, and exit summaries to use palette roles.
- [x] 3.5 Add rendering tests that cover contrast-critical style choices for both light and dark themes.
- [x] 3.6 Improve Markdown rendering for pipe tables, horizontal rules, and terminal-width-aware table wrapping.

## 4. First-Startup Theme Selection

- [x] 4.1 Detect when interactive mode starts without a valid saved `ui.theme`.
- [x] 4.2 Prompt for `auto`, `dark`, or `light` before rendering the welcome panel.
- [x] 4.3 Merge theme selection into missing-API-key setup so first-time users answer configuration prompts in one flow.
- [x] 4.4 Persist the selected theme without discarding existing config fields.
- [x] 4.5 Add tests for first interactive startup with no config, existing config without theme, and existing config with theme.

## 5. Commands And User-Facing Surfaces

- [x] 5.1 Add `deepy config theme` to print saved and resolved themes.
- [x] 5.2 Add `deepy config theme <auto|dark|light>` to persist a selected theme and reject invalid values.
- [x] 5.3 Add `/theme` to interactive slash commands to print saved and resolved themes.
- [x] 5.4 Add `/theme <auto|dark|light>` to persist and apply the selected theme for subsequent interactive output.
- [x] 5.5 Update help text, welcome command tips if appropriate, README/config docs, and tool-facing guidance for the theme commands.
- [x] 5.6 Add `deepy config reset` to remove the existing config file and guide the user through setup again.
- [x] 5.7 Make `/theme` show selectable choices, accept numbered selection, and advise restart after saving.
- [x] 5.8 Replace `/theme` text prompt with keyboard selection and simplify current-theme output.
- [x] 5.9 Use numbered UI theme selection for setup and first-start prompts while keeping theme-name fallback.

## 6. Verification

- [x] 6.1 Run `uv run pytest tests/test_cli.py tests/test_welcome.py tests/test_message_view.py tests/test_terminal_ui.py tests/test_prompt_input.py`.
- [x] 6.2 Run the full `uv run pytest` suite.
- [x] 6.3 Run `uv run ruff check`.
- [x] 6.4 Run `uv run pyright`.
- [x] 6.5 Manually inspect rendered welcome and diff/message output in both light and dark theme modes.
- [x] 6.6 Re-run focused CLI/OpenSpec validation after adding `deepy config reset`.
- [x] 6.7 Re-run focused terminal/slash/OpenSpec validation after improving `/theme` selection.
- [x] 6.8 Re-run focused terminal/slash/OpenSpec validation after adding keyboard theme selection.
- [x] 6.9 Re-run focused CLI/terminal/type/OpenSpec validation after numbered setup theme selection.
- [x] 6.10 Re-run focused Markdown/terminal/type/OpenSpec validation after improving Markdown table rendering.
