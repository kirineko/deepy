## Context

Modern UI is a Textual app with a `VerticalScroll` transcript, a bottom `PromptPanel`, Textual Markdown assistant blocks, a modal `InfoScreen` for `/ps`, and a legacy all-fields reset form for `/reset`. The current behavior makes the transcript hard to browse because prompt history consumes the visible navigation path, the composer grows between one and five rows, `/ps` leaves the conversation surface, and reset asks users to hand-type fields before provider-specific API key guidance is visible.

Classic UI already has the desired reset ordering and selection semantics: select provider, show provider-specific API key URL, enter API key, select model, enter base URL, select thinking, then select UI/theme. Modern UI should reuse those semantics without embedding prompt-toolkit inside the running Textual app.

## Goals / Non-Goals

**Goals:**

- Ensure transcript content can be scrolled with mouse and touchpad wheel input.
- Preserve prompt history from the composer, including ordinary `Up`/`Down` history behavior where the prompt currently owns focus.
- Make the composer a fixed four-line prompt input with internal scrolling for longer drafts.
- Make Markdown tables in transcript output denser without sacrificing readability or autoscroll.
- Display user-invoked `/ps` results in the foreground transcript with identifiers suitable for `/stop`.
- Replace reset free-text editing with a guided flow aligned with Classic UI setup ordering and validation.
- Preserve transcript chronology for tools and local commands unless there is an existing visible tool placeholder to update in place.
- Make model tool result blocks useful at a glance: Todo results show the todo board, model-invoked Shell/CMD results show the command without the model-provided description/comment text, and diff blocks scroll only with the parent transcript.

**Non-Goals:**

- Add transcript `Up`/`Down` keyboard paging as a required behavior.
- Rebuild Classic UI reset; follow-up fixes may add the same restart guidance
  already required for Modern UI when `/reset` changes the running UI or theme.
- Treat AI/tool background-task output as if the user had invoked `/ps`.
- Add new Textual or Markdown runtime dependencies.
- Rework local `!CMD` command rendering; that path has already been optimized and should remain unchanged.

## Decisions

1. Preserve prompt-focused `Up`/`Down` history and fix transcript scroll through scroll-container behavior.

   Textual key events are focus-driven, so one focused widget cannot reliably interpret `Up` as both history recall and transcript scrolling without surprising users. Prompt-focused `Up`/`Down` remains history/navigation; transcript browsing is required through mouse/touchpad wheel and existing transcript/block navigation affordances.

   Alternative considered: move ordinary `Up`/`Down` to transcript scrolling. This would regress the prompt history workflow the user explicitly wants to keep.

2. Use a fixed four-line prompt input.

   The current `PromptPanel` dynamically sets the prompt height between one and five rows. The new behavior should set a stable four-line height and allow Textual's text area to scroll or navigate within longer drafts.

   Alternative considered: keep five rows and only fix overflow. The user specifically requested four fixed rows, and the existing five-row requirement must change.

3. Render user-invoked `/ps` as transcript content.

   `/ps` should append a foreground task summary block only when the user invokes the slash command. Background task output produced by tools remains separate from assistant, thinking, and foreground `/ps` blocks. `/stop` continues to use active task IDs and may accept identifiers from the latest displayed `/ps` block.

   Alternative considered: keep `InfoScreen`. This keeps data out of the transcript but makes it harder to run follow-up `/stop` commands from visible context.

4. Align reset workflow with Classic UI semantics, not prompt-toolkit widgets.

   The Modern UI reset implementation should share ordering, defaults, validation rules, and config write/cancel semantics with Classic UI. It should not mount prompt-toolkit inside Textual because both control terminal input and rendering.

   Alternative considered: improve the existing free-text form. That still requires users to know valid provider/model/thinking/UI values and keeps API key entry before provider-specific guidance.

5. Tighten Markdown table density at the Textual transcript boundary.

   Modern UI currently uses Textual's Markdown widget for assistant output. The implementation can first adjust CSS and Textual Markdown spacing; if that is insufficient, it may introduce a small Deepy-owned table rendering path for transcript Markdown tables.

6. Preserve tool chronology unless a placeholder already anchors the tool.

   Tool calls and outputs should update an existing visible block for the same `call_id`, but a tool output that arrives without a visible placeholder should append at the current transcript tail. Moving every later tool block above the active assistant answer hides genuinely later Shell output after approvals and makes the transcript harder to audit.

   Alternative considered: always insert late tool blocks before the active assistant answer. This fixes one display ordering symptom, but it breaks `/update` approval flows where later Shell output must remain visible near the prompt.

7. Await Textual Markdown updates before autoscrolling assistant output.

   Textual's Markdown widget mounts parsed blocks asynchronously. Assistant Markdown updates should wait for that mount completion before checking the transcript's bottom position, because Markdown tables can change `max_scroll_y` after the synchronous update call returns.

8. Treat audited `tool_call` events as pending approval until the resolver can
   place them.

   Streaming event delivery and audit interruptions are not ordered the same way
   in the UI: a `tool_call` can be queued before the approval resolver has shown
   the matching diff or command prompt. Pending approvals therefore carry the
   `call_id`, and Modern UI suppresses matching running placeholders until the
   approval context is visible and resolved. Approved command placeholders may
   be mounted at the current tail after the decision; rejected or completed
   calls do not later create stale running blocks.

9. Split assistant rendering at visible tool boundaries.

   The run-level assistant buffer remains useful for final output state, but the
   transcript must render visible assistant segments in chronological order.
   When a tool result, local command result, or diff block is actually placed
   after the active assistant block, Modern UI closes that assistant segment.
   Subsequent assistant deltas start a new assistant block at the tail instead
   of updating the older block above tool output. Existing placeholders that are
   already before the assistant remain stable and can still be updated in place
   without splitting the assistant text.

10. Render Todo tool output as a compact transcript board.

   Todo tool output already has structured task metadata and should not be
   reduced to a single `Todo ok` status line. Modern UI should show a compact
   board that fits the existing transcript language: one lightweight progress
   row, a current-task row when present, and a short task list using the
   existing role marker and muted block styling rather than a heavy nested
   panel. The board can truncate long todo lists, but it should leave the
   active and pending work visible enough for the user to inspect.

   Alternative considered: show raw todo JSON or a generic tool details block.
   This would make the transcript noisy and would not match the rest of the
   Modern UI transcript.

11. Keep model Shell/CMD display command-only.

   This follow-up applies to model-invoked Shell/CMD tool calls and results,
   not local `!CMD` commands. The visible command text should come from the
   `command` field only. Model-provided descriptions are still useful for the
   model/tool contract, but the transcript and inline approval summary should
   not display them as shell comments such as `# run tests`, because that makes
   the executable command harder to audit.

   Alternative considered: keep `command  # description` in TUI summaries.
   That provides extra prose, but the user explicitly wants only the command on
   this surface.

12. Let transcript diff blocks use only the parent scroll.

   Modern UI already truncates large rendered diffs. A transcript diff block
   should therefore render as normal transcript content and allow the parent
   transcript scroller to own vertical movement. Nested vertical scrolling in
   a diff block creates a double-scroll path that is noticeably slower and
   harder to control.

   Alternative considered: keep a max-height inner diff scroller for large
   diffs. That protects transcript height, but it recreates the double-scroll
   behavior this follow-up is meant to remove.

## Risks / Trade-offs

- Wheel scrolling may still be affected by focus or child widget overflow behavior -> cover with headless tests around `VerticalScroll` scroll position and avoid nested widgets stealing vertical wheel events unnecessarily.
- Fixed composer height can hide more transcript lines than a one-line draft -> four lines is the requested stable trade-off, and internal draft scrolling prevents unbounded growth.
- Rendering `/ps` in the transcript adds user-requested management content to conversation history -> limit this to explicit user slash-command invocation and keep automatic/tool task output out of that block.
- Reset flow reuse can duplicate Classic UI helper logic if not factored carefully -> reuse existing provider/model/thinking/UI selection functions or extract shared pure helpers rather than copying policy.
- Tool ordering has provider-specific event timing variance -> prefer existing `call_id` placeholders and current arrival order over guessing hidden chronology.
- Audited tool-call suppression depends on `call_id`; when a provider omits it,
  Modern UI can only fall back to conservative tool-name/argument matching, so
  tests cover the normal SDK path where the id is available.
- Splitting assistant blocks changes tests that previously treated an entire
  turn as one visible assistant block; keep the run-level assistant buffer for
  final state while testing visible block ordering separately.
- Awaiting Markdown updates during streaming may add a small amount of UI work per assistant delta -> keep the change scoped to assistant block updates and cover table-heavy autoscroll behavior.
- Rendering Todo boards inline adds more content to the transcript -> keep the
  layout compact, truncate long lists, and avoid card-like or nested-scroll
  treatment.
- Command-only Shell/CMD display removes description prose from the TUI
  transcript and approval surface -> keep descriptions available in the tool
  argument/schema path if needed, but do not render them as comments in Modern
  UI command summaries.
- Removing inner diff scrolling can make each rendered diff block taller ->
  rely on existing diff truncation and parent transcript scrolling rather than
  introducing another scroll container.
