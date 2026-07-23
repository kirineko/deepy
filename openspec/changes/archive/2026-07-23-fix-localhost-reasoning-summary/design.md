## Context

Deepy localhost uses OpenAI Agents SDK `OpenAIResponsesModel`. Stream display
depends on `response.reasoning_summary_text.delta` events, which
`normalize_stream_event` already maps to `reasoning_delta`.

Local CLIProxyAPI returns encrypted reasoning without summary text when only
`reasoning.effort` is set. With `reasoning.summary` set to `auto`/`detailed`,
it streams summary deltas that Deepy can show.

## Goals / Non-Goals

**Goals:**

- Request Responses reasoning summaries for enabled localhost thinking modes.
- Keep effort mapping (`none`/`low`/`medium`/`high`/`xhigh`) unchanged.
- Cover the regression with a focused model-settings test.

**Non-Goals:**

- Changing Chat Completions suggestion settings.
- Switching localhost off Responses API.
- Exposing raw encrypted chain-of-thought.

## Decisions

1. Use `summary="auto"` when effort is not `none`.

   `auto` lets the provider choose an appropriate summary verbosity and is
   sufficient for Deepy's Thinking UI. Alternatives `concise`/`detailed` are
   unnecessary for this bugfix.

2. Omit `summary` when effort is `none`.

   Disabled thinking should not request summary generation.

## Risks / Trade-offs

- [Risk] Some proxy builds may still omit summary text. → Mitigation: keep
  effort/summary request contract; UI already no-ops when no deltas arrive.
- [Trade-off] Summary text is shorter than full CoT / chat
  `reasoning_content`. Acceptable because Responses path only exposes summaries.
