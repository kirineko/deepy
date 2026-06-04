## Context

Deepy currently exposes mixed model-facing tool names such as `modify`,
`WebFetch`, and `AskUserQuestion`. Terminal output reuses those names directly
for most progress lines, while write/edit diff previews introduce separate
English labels such as `Wrote` and `Edited`. DeepSeek thinking is collected but
the visible flushed summary is collapsed and truncated. AskUserQuestion already
has a working protocol and terminal flow, but the model guidance is conservative
and the user-facing custom-answer option appears as a generic `Other` entry.

The change should improve the human-facing terminal experience without changing
the function-tool names, tool result JSON shape, pending-question parser, or
session replay contract.

## Goals / Non-Goals

**Goals:**

- Present all tool activity through a consistent user-facing display style.
- Preserve existing model-facing tool identifiers and stored session data.
- Make tool names visually prominent using one shared treatment for every tool.
- Bring write/edit preview headers into the same visual vocabulary as other
  tool activity.
- Print DeepSeek thinking immediately and completely as it streams, using the
  same label family as tool activity.
- Encourage DeepSeek to use the user's language for thinking, especially Chinese
  thinking for Chinese user requests.
- Increase AskUserQuestion's practical trigger rate through clearer prompt and
  tool-description guidance.
- Make custom answers in AskUserQuestion prompts look intentional and localized.

**Non-Goals:**

- Renaming FunctionTool registrations or changing tool JSON result names.
- Adding a new terminal UI framework or dependency.
- Showing different colors for different tools.
- Removing the defensive clarification-round limit.
- Guaranteeing DeepSeek's private internal reasoning language beyond prompt
  guidance and displayed reasoning deltas.

## Decisions

1. Keep protocol names stable and add display labels.

   Tool registration and results keep names such as `WebFetch` and
   `AskUserQuestion`. The UI derives a display label for transcript/status
   output, using a stable display convention such as `[WebFetch]`, `[Write]`,
   `[Modify]`, `[Read]`, and `[AskUserQuestion]`. This avoids migration risk
   for existing session history and tests while making terminal output
   consistent.

   Alternative considered: rename the tools themselves. Rejected because it
   would affect model schemas, session replay, tests, and compatibility with
   existing histories.

2. Use one visual treatment for all tool names.

   Tool labels should be visually distinct from parameters and status, but the
   distinction should not depend on a per-tool color map. A good default is a
   bold bracketed label such as `[WebFetch]`, using the existing palette's tool
   style. Status (`ok`, `failed`, waiting state) can continue using success or
   error styling.

   Alternative considered: different colors per tool. Rejected because the user
   requested uniform visual characteristics and because per-tool colors increase
   theme complexity.

3. Treat write/edit preview headers as tool result headers.

   Diff previews should no longer lead with standalone verbs like `Wrote` or
   `Edited`. Instead, they should render with the same tool label style and a
   concise action/result phrase, for example `[Write] path (+1 -0)` or
   `[Modify] path (+1 -1)`. The exact text can stay compact, but the first
   visual token should match other tool output.

   Alternative considered: keep `Wrote`/`Edited` but style them like tool names.
   Rejected because it still creates a separate naming system.

4. Render thinking immediately with the same label family.

   Thinking deltas should print to the transcript as they arrive, headed by a
   `[Thinking]` label that follows the same bracketed, prominent visual
   treatment as tool labels. The renderer should not maintain separate summary
   versus transcript truncation behavior for thinking content; all received
   thinking text should be visible immediately and completely.

   Alternative considered: keep live status summarized and only print full
   thinking at flush boundaries. Rejected after visual validation because the
   delayed summary/full-output split made thinking behavior harder to reason
   about and did not match the desired terminal rhythm.

5. Improve language and question prompting through prompt text, not a new
   runtime heuristic.

   The system prompt should instruct DeepSeek to match thinking language to the
   user's latest natural language. AskUserQuestion tool documentation and schema
   description should trial Chinese-first wording that explicitly names the
   useful cases: ambiguity, preferences, scope, implementation trade-offs, and
   required approval.

   Alternative considered: detect language in Python and inject per-turn dynamic
   prompt fragments. Rejected for this change because the stable system/tool
   prompt is simpler and enough to test the behavior direction.

6. Make the custom-answer option explicit and localized.

   The terminal prompt should present the custom answer option with a clearer
   label such as `Custom answer` in English contexts and `自定义回答` in Chinese
   contexts, instead of always appending a bare `Other`. The answer protocol can
   still serialize custom text through the existing internal sentinel.

   Alternative considered: remove the custom option and only accept free text.
   Rejected because numbered options plus custom input is useful for fast
   terminal selection.

## Risks / Trade-offs

- Existing tests assert exact strings for tool summaries -> Update tests around
  display labels while keeping protocol-level assertions unchanged.
- Full thinking can be long -> Print it directly and rely on terminal scrollback;
  avoid additional truncation logic in the thinking renderer.
- Prompt changes may over-trigger AskUserQuestion -> Keep explicit guidance to
  proceed on low-impact details and retain the existing clarification-round
  limit.
- Chinese-first AskUserQuestion guidance may affect English sessions -> Phrase
  the rule as language matching: ask in Chinese when the user uses Chinese,
  otherwise match the user's language.
- Uniform tool styling may reduce quick visual scanning by tool category ->
  Preserve status coloring and concise parameter summaries so users can still
  distinguish action and outcome.
