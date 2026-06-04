## Context

The current interactive footer is assembled from two layers:

- `src/deepy/ui/terminal.py` builds the status text: model, reasoning mode, CWD, AGENTS.md, MCP, and context window usage.
- `src/deepy/ui/prompt_input.py` renders that text as the prompt-toolkit bottom toolbar and appends permanent input help.

During model and local-command work, Deepy uses Rich status renderers instead of the prompt-toolkit bottom toolbar. That makes the current footer effectively an idle-prompt surface, while active turns use a separate working-status message. The display strings also mix styles such as `model ...`, `thinking ...`, `ctx win ...`, `MCP ...`, and `AGENTS.md loaded`.

## Goals / Non-Goals

**Goals:**

- Use one compact status-footer model for idle prompt input, model work, and local command work.
- Merge model and reasoning into a single leading segment such as `model deepseek-v4-pro[max]`.
- Preserve current context-window accounting while shortening the label to `ctx`.
- Use compact loaded indicators: `mcp N` and `[AGENTS.md]`.
- Remove persistent exit help from the footer without changing Ctrl+D behavior.
- Improve footer visual hierarchy in dark and light themes.

**Non-Goals:**

- Change Enter, Ctrl+J, Ctrl+D, Esc, slash command, or local command behavior.
- Change session context accounting, compaction thresholds, or usage footer semantics.
- Change model selection configuration, MCP connection behavior, or AGENTS.md discovery rules.
- Add a new terminal UI framework or dependency.

## Decisions

1. Build a reusable footer segment model instead of formatting one flat string early.

   The footer needs different visual emphasis for stable identity, loaded indicators, active work, separators, and muted context. A segment model can render to prompt-toolkit tuples for idle input and to Rich text for active work without duplicating formatting rules.

   Alternative considered: keep returning a single string and style it all as `toolbar.context`. Rejected because it cannot provide visual hierarchy without brittle parsing.

2. Make the compact model segment the first footer segment.

   The leading segment should be the active model identity with a lowercase key: `model deepseek-v4-pro[max]`, `model deepseek-v4-pro[high]`, or `model deepseek-v4-pro[none]`. This keeps the key/value style consistent with `cwd`, `mcp`, `ctx`, and `newline` while still avoiding a separate `thinking` label.

   Alternative considered: `model: deepseek-v4-pro · reasoning: max`. Rejected because it remains longer than necessary and keeps label noise in the most stable part of the footer.

3. Use `ctx` as the context label.

   `ctx` is shorter than `context`, already familiar in developer terminal UIs, and avoids the current redundant `ctx win` label. The values and percentage continue to represent Context Window occupancy.

   Alternative considered: `context`. It is clearer for first-time users, but longer and visually heavier. The welcome panel, usage footer, and specs can continue to spell out Context Window where needed.

4. Reserve a terminal bottom line for running status in TTY output.

   Prompt-toolkit owns the true fixed bottom toolbar while Deepy is collecting input. During model work or local command work, Deepy should reserve the terminal's last row as a status footer by setting the scroll region to the rows above it, then write status updates directly to the reserved row without a newline. This keeps normal transcript and command output scrolling above the footer instead of carrying footer fragments through scrollback.

   Running work uses two reserved rows. The last row keeps the same compact footer content and toolbar background as the idle prompt footer. The row above it is a separate realtime status row with a stronger visual treatment for an animated spinner, `time ...`, `esc to interrupt`, and the current state (`thinking`, `tool ...`, `local command`). Runtime-only fields are not printed into the normal transcript, and thinking transcript text remains in the normal output area above both reserved rows.

   In the light theme, the running compact footer row should reuse the completed prompt footer's toolbar background so the bottom row does not flip between gray during work and the softer completed-prompt tint after the turn finishes. It should also preserve footer segment emphasis, including the bold model identity. The realtime status row above it keeps the stronger warning-background treatment because that row's purpose is active work visibility.

   Alternative considered: force prompt-toolkit bottom toolbar to persist during Rich output. Rejected because prompt-toolkit owns only the prompt-input lifecycle and mixing the two render loops would increase flicker and platform risk.

   Alternative considered: keep embedding the full footer in Rich `console.status()`. Rejected because that status follows the current output stream rather than staying fixed at the terminal bottom.

   Alternative considered: draw a custom ANSI bottom overlay without changing the scroll region. Rejected after terminal testing showed that refresh sequences can still appear as repeated status fragments in real scrollback.

5. Use bracket and lowercase conventions deliberately.

   Footer keys use lowercase (`ctx`, `mcp`, `cwd`, `compact next`) for consistency. The AGENTS indicator uses `[AGENTS.md]` because the filename is case-sensitive and the brackets provide a visible loaded marker without the extra word `loaded`.

   Footer emphasis is title-only: `model`, `cwd`, `mcp`, `ctx`, and `newline` are bold, while their values are normal weight. `[AGENTS.md]` is also bold as a loaded indicator. Prompt-toolkit and ANSI running-footer rendering must share this segmentation, and ANSI output must explicitly reset bold before normal-value spans.

   Alternative considered: `agents: loaded`. Rejected because it loses the exact file name users recognize and could imply a generic feature rather than the specific instruction file.

6. Add visual roles but keep one coordinated color family.

   The implementation should use existing theme palette concepts and add narrow footer roles only if needed, such as identity, loaded indicator, active work, muted path/context, and separator. These roles should not produce unrelated color blocks; identity and active state can use weight, while the text color remains coordinated and separators use lower contrast.

   Alternative considered: rely on the existing single toolbar foreground/context colors. Rejected because the user explicitly asked to improve the visual effect, and the current one-style treatment makes the compact footer harder to scan.

## Risks / Trade-offs

- [Risk] Rich status output can still visually differ from prompt-toolkit toolbar rendering across terminals. -> Mitigation: share the same segment content builder and theme role names, then test the rendered text and style tuple structure separately.
- [Risk] Removing persistent `Ctrl+D twice exit` may reduce discoverability. -> Mitigation: preserve the existing one-press confirmation prompt and keep Ctrl+D behavior covered by tests.
- [Risk] `ctx` may be less obvious than `context` to a new user. -> Mitigation: keep Context Window terminology in welcome/status/help surfaces where explanatory text is appropriate; keep the footer compact.
- [Risk] Adding too many style roles can make the palette harder to maintain. -> Mitigation: add only footer-specific roles that map directly to visible hierarchy, and reuse existing palette colors where they already fit.
