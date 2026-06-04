## 1. Theme And Visual Foundation

- [x] 1.1 Audit every current TUI interaction surface and classify it as inline transcript, composer-adjacent, side/detail surface, or justified management screen.
- [x] 1.2 Add a TUI theme mapping helper that maps shared `dark` to `atom-one-dark` and shared `light` to `atom-one-light`.
- [x] 1.3 Update Textual app theme application to use the mapping while preserving stable UI `dark` / `light` settings.
- [x] 1.4 Add tests proving stable UI theme validation still accepts only shared values and TUI resolves those values to curated Textual themes.
- [x] 1.5 Reduce default TUI chrome by replacing heavy borders with lighter separators, semantic color, and theme-aware background layers.
- [x] 1.6 Add narrow and wide layout tests for the new visual foundation.

## 2. Transcript Experience Redesign

- [x] 2.1 Define transcript display models for assistant, user, reasoning, tool, diff, error, usage, info, and decision content, including role identity, state, metadata, folded details, and visual priority.
- [x] 2.2 Redesign `You` / `Deepy` / tool / question identity presentation so short turns are compact and scannable without large repeated headers.
- [x] 2.3 Replace or soften the current heavy left rail/stripe treatment with a lightweight theme-aware gutter or semantic marker that supports scanning and focus.
- [x] 2.4 Define and implement dense Markdown presentation rules for paragraphs, headings, lists, tables, code blocks, links, and inline emphasis.
- [x] 2.5 Rework transcript block widgets to use reduced vertical whitespace, coherent grouping, and folded metadata/detail regions across all content types.
- [x] 2.6 Move repeated usage/cache/context metadata into compact turn footers, status summaries, or folded details where possible.
- [x] 2.7 Preserve expand/collapse, block focus, scroll position, Markdown readability, and new-output behavior after the transcript renderer changes.
- [x] 2.8 Add tests and visual smoke coverage for dense rendering of long Markdown replies, short user prompts, tool calls, diffs, errors, questions, usage metadata, and inline decisions.

## 3. Integrated Composer And Attachments

- [x] 3.1 Redesign `PromptPanel` as one integrated composer surface with prompt input, action hints, attachment row, suggestion overlay, and busy state.
- [x] 3.2 Add focusable/removable image attachment items that stay outside the editable prompt text.
- [x] 3.3 Implement keyboard deletion for selected attachments without altering prompt text.
- [x] 3.4 Ensure prompt submission sends exactly the remaining attachments after deletion.
- [x] 3.5 Add tests for attachment display, single attachment deletion, multiple attachment deletion, prompt preservation, and submission payloads.
- [x] 3.6 Add tests that slash suggestions, file suggestions, generated input suggestions, attachment row, and prompt text do not overlap in narrow and wide terminals.

## 4. Live Activity Feedback

- [x] 4.1 Add a reduced-motion or deterministic animation policy for tests.
- [x] 4.2 Add live assistant streaming state, such as a cursor, pulse, or activity marker, that updates during long replies.
- [x] 4.3 Add running tool state feedback and terminal-state transitions for success, failure, waiting, and retryable tool outcomes.
- [x] 4.4 Add an animated or changing new-output indicator when the user is scrolled away from the bottom.
- [x] 4.5 Add tests proving activity indicators update without stealing focus, corrupting scroll position, or making headless tests flaky.

## 5. Inline Decision Blocks

- [x] 5.1 Define a reusable inline interaction framework for transcript decision blocks and composer-adjacent short-choice surfaces.
- [x] 5.2 Implement an inline audit decision block with summary, metadata, preview/diff detail, Approve/Reject options, and completed state.
- [x] 5.3 Replace `AuditApprovalScreen` usage for runtime audit approvals with inline audit decision blocks.
- [x] 5.4 Implement inline AskUserQuestion decision blocks for single-select, multi-select, custom answer, cancel, and same-session continuation.
- [x] 5.5 Migrate frequent short-choice command flows away from blocking modals where an inline or composer-adjacent surface preserves the main flow.
- [x] 5.6 Ensure pending inline decisions focus correctly and make composer state clear while preserving transcript navigation.
- [x] 5.7 Add tests for audit approve/reject, diff preview expansion, AskUserQuestion answer modes, cancellation, short-choice flows, and continuation.

## 6. Management Workflow Redesign

- [x] 6.1 Redesign session browsing/resume management to prefer non-disruptive inline, side, or embedded flow when practical, with compact metadata, readable preview, active-session marker, keyboard search/navigation, cancellation, and focus restoration.
- [x] 6.2 Redesign skills management and skill market as a justified management surface with clearer installed/market separation, visible action affordances, compact action rows, readable long detail views, and predictable install/update/uninstall/use outcomes.
- [x] 6.3 Redesign reset/config workflow as a guided provider-aware form or staged flow with field-local validation, explicit save/cancel outcomes, and preserved settings on cancellation.
- [x] 6.4 Redesign help/status/MCP/model/skill detail surfaces with compact sections, grouped content or tabs where useful, lighter chrome, and no persistent `Footer` when a command strip is sufficient.
- [x] 6.5 Keep management workflows screen-based only where leaving the conversation flow is intentional and documented by the interaction audit, and restore conversation focus predictably when they close.
- [x] 6.6 Rewrite any retained modal/screen visual design so it matches the polished TUI system instead of preserving current UI chrome.
- [x] 6.7 Add regression tests for sessions, skills, reset/config, help/status/detail cancellation, selection, action execution, validation feedback, and return-to-conversation focus.

## 7. Documentation And Validation

- [x] 7.1 Update English and Chinese README/UI documentation for compact transcript, integrated composer, attachment deletion, live activity, inline decisions, and curated Textual theme mapping.
- [x] 7.2 Remove or replace stale screenshots that no longer match the polished TUI.
- [x] 7.3 Run `openspec validate polish-textual-tui-experience --type change --strict`.
- [x] 7.4 Run focused Textual TUI tests for interaction-surface classification, transcript Markdown rendering, role identity, gutter/rail treatment, composer, themes, animation policy, inline audit, AskUserQuestion, short-choice flows, sessions, skills, reset/config, help/status/detail views, and layout.
- [x] 7.5 Run focused stable UI tests for unchanged shared theme behavior.
- [x] 7.6 Run `uv run ruff check src tests`.
- [x] 7.7 Run `uv run ty check src`.
- [x] 7.8 Run `uv run pytest -q`.
- [x] 7.9 Manually validate the polished TUI in the current terminal with long streaming output, attachment deletion, theme switching, inline audit approval, inline AskUserQuestion, sessions, skills, reset/config, and narrow/wide terminal sizes.

## 8. Follow-up Visual Polish

- [x] 8.1 Replace attachment chip `x` markers with a clear keyboard deletion hint and keep attachment removal operable from the composer.
- [x] 8.2 Replace literal `You` / `Deepy` transcript labels with lighter role markers while preserving scannability and live assistant state.
- [x] 8.3 Remove per-turn usage/cache/context metadata from the persistent footer unless the user opens an explicit status/detail view.
- [x] 8.4 Change the curated dark default to a calmer Textual theme and keep assistant text contrast readable.
- [x] 8.5 Expand the TUI `/theme` picker with multiple supported Textual built-in themes while preserving stable UI `dark` / `light` compatibility.
- [x] 8.6 Update tests and documentation for the follow-up visual polish.
- [x] 8.7 Run OpenSpec validation and focused TUI/config tests.

## 9. Follow-up Marker And Attachment Polish

- [x] 9.1 Change the default dark Textual mapping to `tokyo-night`.
- [x] 9.2 Render user and assistant role markers inline with the first content line, with stronger theme-aware color and weight.
- [x] 9.3 Make attachment selection and deletion reachable from the focused prompt input.
- [x] 9.4 Update tests and documentation for inline markers, `tokyo-night`, and prompt-local attachment deletion.
- [x] 9.5 Run OpenSpec validation and focused TUI/config tests.

## 10. Follow-up Attachment Shortcuts

- [x] 10.1 Replace modifier-key attachment selection with Down-arrow entry and cycling.
- [x] 10.2 Use Backspace to remove an explicitly selected attachment while preserving normal text deletion otherwise.
- [x] 10.3 Update tests and documentation for Down-arrow attachment selection.
- [x] 10.4 Run OpenSpec validation and focused TUI tests.

## 11. Follow-up Attachment Selection Mode

- [x] 11.1 Make Down enter attachment selection mode without forcing deletion to return to input.
- [x] 11.2 Support Left/Right attachment movement while selection mode is active.
- [x] 11.3 Support Up to exit attachment selection mode and restore normal input behavior.
- [x] 11.4 Update tests and documentation for attachment selection mode.
- [x] 11.5 Run OpenSpec validation and focused TUI tests.

## 12. Follow-up Compact Tool Transcript

- [x] 12.1 Hide tool parameters and output bodies from the default TUI transcript.
- [x] 12.2 Render tool call/result entries with the same marker-and-content line structure as user and assistant turns.
- [x] 12.3 Preserve tool status, retry, recovery, and detail data internally for behavior that depends on it.
- [x] 12.4 Update tests and documentation for compact tool transcript rendering.
- [x] 12.5 Run OpenSpec validation and focused TUI tests.

## 13. Follow-up Diff And Native Input Polish

- [x] 13.1 Render successful file edit diffs directly without visible `Write ok` / `Update ok` or `Diff` label rows.
- [x] 13.2 Ensure successful file edit diffs appear after the assistant text and use relative paths under the project root.
- [x] 13.3 Add subtle output turn spacing to distinguish subsequent turns.
- [x] 13.4 Remove the custom TUI keyboard-protocol decoding patch and rely on Textual native input.
- [x] 13.5 Update tests and documentation for direct diff rendering and native input.
- [x] 13.6 Run OpenSpec validation and focused TUI tests.
