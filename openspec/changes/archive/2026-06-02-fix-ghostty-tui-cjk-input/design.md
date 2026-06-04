## Context

The current Textual TUI relies on Textual-native `TextArea` input. Textual 8.2.6 enables Kitty keyboard protocol during terminal startup with `ESC[>1u`, but its parser only handles a subset of CSI-u key forms. Ghostty emits Chinese IME text commits as associated-text sequences such as `ESC[32;;20320:22909u`, where the associated text can contain multiple Unicode code points separated by `:`.

When Textual does not parse that sequence, the remaining printable bytes are reissued into the focused `TextArea`, so the prompt receives literal `[32;;...u` text. This is not a prompt rendering issue and should not be fixed by scanning and replacing prompt contents after insertion.

Textual 8.2.7 introduces `TEXTUAL_DISABLE_KITTY_KEY`, which prevents Textual from enabling Kitty keyboard protocol on startup. Deepy's TUI runner imports `deepy.tui.app` lazily, so the startup path can set this environment variable before any Textual modules are imported.

## Goals / Non-Goals

**Goals:**

- Restore stable CJK IME input in Ghostty for the Textual TUI.
- Avoid prompt-content mutation or post-insertion decoding workarounds.
- Keep the default `deepy` stable UI path untouched.
- Let advanced users opt back into Kitty keyboard protocol through the environment.

**Non-Goals:**

- Implement a full Kitty keyboard protocol parser in Deepy.
- Patch Textual internals or vendor Textual code.
- Guarantee every enhanced-key combination remains distinguishable when the default TUI disables Kitty keyboard protocol.

## Decisions

- Upgrade to Textual 8.2.7 instead of carrying a Deepy-local decoder. This gives Deepy a supported environment switch and keeps protocol handling owned by Textual.
- Set `TEXTUAL_DISABLE_KITTY_KEY=1` with `os.environ.setdefault()` in `run_tui()` before importing `deepy.tui.app`. This keeps the default safe for Ghostty while preserving user override.
- Keep tests at the boundary that matters: verify the current Textual parser failure shape for multi-codepoint associated text, and verify Deepy sets the environment before importing the TUI app path.
- Clean up stale method names in `PromptTextArea` so the code no longer implies prompt-level protocol decoding.

## Risks / Trade-offs

- Disabling Kitty keyboard protocol may reduce enhanced-key disambiguation in the TUI. Mitigation: Deepy's current TUI bindings use conventional keys that remain available, and users can override the environment if they need enhanced protocol behavior.
- Textual may later fix multi-codepoint associated-text parsing. Mitigation: the behavior is easy to revisit because it is isolated to the TUI runner startup guard and dependency version.
- Setting an environment variable inside Deepy affects only the current process after `deepy tui` starts. Mitigation: the stable UI is not in this path, and `setdefault()` respects explicit user configuration.
