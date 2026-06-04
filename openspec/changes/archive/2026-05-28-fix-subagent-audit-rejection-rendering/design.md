## Context

Stable terminal stream rendering currently detects audit rejections by scanning the entire raw tool-output text for `"audit approval"` and `"reject"`. Structured Deepy tool outputs include user-visible report text inside JSON, so a successful subagent result can be misclassified when the report discusses a rejected approval.

## Goals / Non-Goals

**Goals:**

- Render explicit SDK audit-rejection outputs as rejected.
- Render structured successful subagent results as successful even when the report text mentions rejected approvals.
- Keep the fix local to stream display classification.

**Non-Goals:**

- Change SDK approval resolution semantics.
- Change subagent execution, subagent result extraction, or the approval picker UI.
- Add new user configuration.

## Decisions

- Classify audit rejection only when the parsed tool output is not an explicit success. This preserves the existing raw SDK rejection path while preventing successful structured outputs from being overridden by text in their body.
- Pass the already-parsed `ToolOutputView` into the rejection detector instead of reparsing raw output. The stream handler already parses once for normal rendering, and this keeps the decision tied to the same view used for status and output formatting.

## Risks / Trade-offs

- A tool could technically return `ok: true` while meaning "this operation was rejected." That is already contradictory structured data; Deepy should trust the explicit success flag for display status and show the rejection detail in the body.
- Raw SDK rejection text remains substring-based because that is the only signal available for that legacy path. Focused tests keep the intended behavior stable.
