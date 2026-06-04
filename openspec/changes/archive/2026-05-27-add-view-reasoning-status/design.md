## Context

The stable terminal UI currently streams reasoning text into the transcript as soon as `reasoning_delta` events arrive and updates runtime status with a coarse `thinking` detail. The Textual TUI also renders reasoning blocks from normalized stream events. Deepy already estimates token counts for streamed text and tracks per-turn progress in app state, but the stable runtime status does not expose a concise live token counter.

Deepy also already uses `/compact` for context compaction and `/model thinking ...` for provider reasoning configuration. The new command must avoid those meanings and stay clearly scoped to display mode.

## Goals / Non-Goals

**Goals:**

- Default all users to a concise view that hides live reasoning transcript text.
- Provide `/view`, `/view toggle`, `/view concise`, and `/view full` forms.
- Persist view mode in TOML as a UI display preference.
- Keep model reasoning strength and provider request behavior unchanged.
- Show a live per-turn cumulative stream token estimate in runtime status as `↓ N tokens`.
- Keep the stream token estimate moving across reasoning and assistant output deltas when both are streamed in the same model turn.
- Preserve parity between the stable terminal UI and the experimental Textual TUI.

**Non-Goals:**

- Do not rename or change `/compact`; it remains context compaction.
- Do not change `/model thinking`, provider reasoning effort, or model selection semantics.
- Do not attempt to make live token counts billing-accurate; final provider usage remains authoritative.
- Do not require providers to stream fields they do not currently expose.
- Do not add a new external tokenizer dependency.

## Decisions

1. **Use `view_mode = "concise" | "full"` under `[ui]`.**

   `concise` means live reasoning transcript text is hidden. `full` means the existing reasoning/thinking block is rendered. This keeps the configuration name tied to UI display instead of model reasoning behavior.

   Alternative considered: `show_thinking_content = true | false`. Rejected because the setting name repeats "thinking" and can be confused with model reasoning configuration.

2. **Use `/view` as the command namespace.**

   `/view` and `/view toggle` switch between concise and full, `/view concise` hides reasoning text, and `/view full` shows reasoning text. Confirmation text includes `reasoning hidden` or `reasoning shown`.

   Alternatives considered: `/thinking`, `/reasoning`, and `/compact`. `/thinking` and `/reasoning` sound like model behavior. `/compact` is already context compaction.

3. **Define `↓ N tokens` as current-turn stream progress, not reasoning-only usage.**

   The counter resets at the start of each model turn and increments from streamed reasoning, assistant text, and tool-call argument deltas. This keeps the status active when a model transitions from hidden reasoning to visible output or spends time preparing a large tool call, and matches the familiar `↓ tokens` convention from other agent UIs.

   Alternative considered: count reasoning deltas only. Rejected because the value can stop changing during the gap between reasoning and final output, making the UI look stalled.

4. **Keep live estimates separate from final usage.**

   Runtime status uses local token estimation for responsiveness. Final usage and cost/status summaries continue using provider usage fields such as `reasoning_tokens`, `prompt_tokens`, `completion_tokens`, and cache details when available.

5. **Count streamed tool-call argument text when available.**

   Deepy's normalized raw-response events already expose function-call argument deltas as text. Counting those deltas keeps the status moving during large Update/Write calls without changing persisted messages or final provider usage accounting.

## Risks / Trade-offs

- **Estimate differs from provider billing** -> Label the runtime value only as `↓ N tokens` and keep exact usage in existing usage summaries.
- **Some providers do not stream output text** -> The elapsed time and interrupt hint remain visible; the token count only updates when Deepy receives streamable text.
- **Users confuse view mode with model reasoning mode** -> Command/help text must say reasoning is hidden or shown, not enabled or disabled.
- **Hiding reasoning might accidentally drop persisted data** -> Apply view mode only at rendering time; session persistence and provider event normalization remain unchanged.
- **Stable UI and Textual TUI drift** -> Add focused tests for both surfaces and update shared slash-command discovery where possible.
