## 1. Footer Model And Formatting

- [x] 1.1 Add a reusable interactive status footer builder that produces structured segments for model/reasoning, active work, CWD, context, AGENTS.md, MCP, and separators.
- [x] 1.2 Format model and reasoning as one leading segment, for example `model deepseek-v4-pro[max]`, `model deepseek-v4-pro[high]`, or `model deepseek-v4-pro[none]`.
- [x] 1.3 Change Context Window footer text from `ctx win ...` to a compact `ctx ...` segment while preserving the existing usage source, totals, percentage, remaining-token display, and `compact next` behavior.
- [x] 1.4 Change MCP footer text to `mcp N` when active MCP servers exist.
- [x] 1.5 Change AGENTS.md footer text from `AGENTS.md loaded` to `[AGENTS.md]`, preserving the exact filename casing.
- [x] 1.6 Remove persistent `Ctrl+D twice exit` help from the footer while preserving Ctrl+D confirmation behavior and message.

## 2. Visual Treatment

- [x] 2.1 Add or reuse theme palette roles for footer identity, active-work state, loaded indicators, muted metadata, and separators.
- [x] 2.2 Render idle prompt footer segments with prompt-toolkit formatted text tuples so model identity, loaded indicators, separators, and metadata are visually distinct.
- [x] 2.3 Render active model and local-command work statuses with the same footer segment content and comparable Rich styling.
- [x] 2.4 Verify light and dark theme footer colors remain readable and do not collapse into one undifferentiated style.

## 3. Runtime Integration

- [x] 3.1 Update idle prompt input to use the new structured footer renderer.
- [x] 3.2 Update model-turn working status refresh to keep stable footer segments visible while active work details change.
- [x] 3.3 Update local `!` command working status to use the same compact footer model.
- [x] 3.4 Ensure slash commands that update model, theme, session, compaction, skills, MCP, or AGENTS-related state refresh the footer before the next prompt.

## 4. Tests And Verification

- [x] 4.1 Update prompt-input tests for removal of persistent `Ctrl+D twice exit` footer help and for structured visual footer tuples.
- [x] 4.2 Update terminal footer tests for `model deepseek-v4-pro[max]`, `ctx ...`, `mcp N`, `[AGENTS.md]`, lowercase segment labels, and absence of `ctx win`, separate `thinking `, and `AGENTS.md loaded`.
- [x] 4.3 Add or update interactive-loop tests proving idle prompt, model work, and local command work all receive compact footer status.
- [x] 4.4 Run targeted tests for prompt input, terminal UI, agent-instructions footer behavior, MCP footer behavior, and context footer behavior.
- [x] 4.5 Run `openspec validate improve-status-footer --type change --strict`.

## 5. Screenshot Feedback Fixes

- [x] 5.1 Render running model and local-command status on a reserved terminal-bottom line instead of emitting the full footer as an ordinary Rich status line.
- [x] 5.2 Normalize footer colors to one coordinated foreground family with lower-contrast separators instead of mixed blue/yellow/green/gray segment blocks.
- [x] 5.3 Add tests for reserved bottom-line status behavior and coordinated toolbar palette roles.

## 6. Prompt Help Follow-up

- [x] 6.1 Restore the `newline: ctrl+j` hint in the prompt bottom footer while keeping `Ctrl+D twice exit` hidden from the persistent footer.

## 7. Running Footer Follow-up

- [x] 7.1 Keep thinking transcript text and thinking summaries out of the running status footer.
- [x] 7.2 Keep runtime-only fields (`time`, `esc to interrupt`, and current state) in the fixed footer rather than normal transcript output.
- [x] 7.3 Keep the running footer visually aligned with the idle prompt footer and fill the reserved footer row background.
- [x] 7.4 Add regression tests for concise thinking status updates and running footer content.

## 8. Two-Line Running Status Follow-up

- [x] 8.1 Restore immediate thinking text streaming without waiting for the reasoning buffer threshold.
- [x] 8.2 Split runtime status into a separate highlighted line above the compact footer.
- [x] 8.3 Keep the compact footer's bottom-row background style unchanged during running work.
- [x] 8.4 Add regression tests for the two reserved rows and separated runtime/footer content.

## 9. Footer Copy And Idle Background Follow-up

- [x] 9.1 Keep the idle prompt footer background aligned with the running footer by disabling prompt-toolkit reverse rendering for toolbar classes.
- [x] 9.2 Standardize footer copy as `model ...`, `mcp N`, and `newline: ctrl+j`.
- [x] 9.3 Update tests and OpenSpec text for the final footer copy.

## 10. Runtime Spinner Follow-up

- [x] 10.1 Add an animated spinner to the realtime running status line before elapsed time.
- [x] 10.2 Refresh the realtime status line frequently enough for spinner movement without changing the compact footer row.
- [x] 10.3 Add regression coverage for spinner rendering and frame advancement.

## 11. Light Theme Bottom Footer Color Follow-up

- [x] 11.1 Reuse the completed prompt footer toolbar tint for the light-theme running compact footer row.
- [x] 11.2 Keep the light-theme realtime status row highlighting unchanged.
- [x] 11.3 Add regression coverage for light-theme running footer and completed footer background alignment.

## 12. Running Footer Segment Style Follow-up

- [x] 12.1 Preserve Rich footer segment styles when drawing the running compact footer row with ANSI.
- [x] 12.2 Add regression coverage for bold model identity in the running compact footer row.

## 13. Footer Title-Only Emphasis Follow-up

- [x] 13.1 Render footer title keys (`model`, `cwd`, `mcp`, `ctx`, `newline`) in bold while keeping values normal weight.
- [x] 13.2 Render `[AGENTS.md]` as a bold loaded indicator.
- [x] 13.3 Explicitly reset ANSI bold before normal-value spans so running footer weight matches completed prompt footer weight.
