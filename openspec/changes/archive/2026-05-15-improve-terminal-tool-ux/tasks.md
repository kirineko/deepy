## 1. Tool Display Formatting

- [x] 1.1 Add a display-label helper that maps model-facing tool names to normalized terminal labels without changing registered tool names or tool result JSON.
- [x] 1.2 Update streamed tool-call and tool-output status rendering to show the normalized label with one shared prominent visual treatment.
- [x] 1.3 Update session-history rendering paths to use the same normalized tool label convention as live streamed output.
- [x] 1.4 Update tool summary tests to assert display-label behavior while preserving protocol-name assertions where applicable.

## 2. Write And Modify Preview Headers

- [x] 2.1 Replace standalone `Wrote` and `Edited` diff preview headers with headers that begin with the same tool-label treatment used by other tool activity.
- [x] 2.2 Preserve changed path, added-line count, removed-line count, and existing diff line rendering behavior.
- [x] 2.3 Update write/modify preview tests so they reject standalone `Wrote` and `Edited` headers and verify the unified tool-label style.

## 2a. Shell Output Display

- [x] 2a.1 Render full captured shell output for shell tool results in a distinct style.
- [x] 2a.2 Reuse shell output rendering for both streamed tool results and session history.
- [x] 2a.3 Add tests for successful and failed shell output visibility.

## 3. Thinking Display And Prompt Guidance

- [x] 3.1 Split thinking formatting so live working status keeps a concise summary but transcript flush prints the complete accumulated thinking text.
- [x] 3.2 Preserve readable line breaks and theme-compatible styling for full thinking transcript output.
- [x] 3.3 Add system prompt guidance that visible thinking should match the user's latest natural language, including Chinese thinking for Chinese user requests.
- [x] 3.4 Add or update tests for full thinking flush output, concise live status behavior, and prompt language guidance.

## 4. AskUserQuestion Guidance And Custom Answer UX

- [x] 4.1 Revise AskUserQuestion tool documentation with Chinese-first, language-matching guidance for ambiguity, preferences, implementation choices, trade-offs, and required approval.
- [x] 4.2 Revise the AskUserQuestion FunctionTool description to encourage appropriate use without asking for low-impact details.
- [x] 4.3 Update AskUserQuestion option rendering so the custom-answer path is explicit and localized when the question language is clear.
- [x] 4.4 Ensure custom-answer display does not leak internal sentinel values into normal user-facing output or model answer text.
- [x] 4.5 Update AskUserQuestion tests for raw-payload suppression, Chinese/custom-answer labels, recommended option guidance, and answer formatting.

## 5. Verification

- [x] 5.1 Run focused tests for terminal UI, message view, AskUserQuestion, prompt generation, and thinking behavior.
- [x] 5.2 Run the broader relevant test suite if focused tests pass.
- [x] 5.3 Manually inspect representative rendered output strings for tool labels, write/modify previews, full thinking flush, and AskUserQuestion custom-answer display.
