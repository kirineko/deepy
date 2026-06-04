## Context

Deepy uses the OpenAI Agents SDK `OpenAIChatCompletionsModel` for DeepSeek,
Xiaomi, and OpenRouter. The SDK has an existing replay path for
`reasoning_content`: when a reasoning item appears before a function call, the
converter can attach that reasoning text back to the replayed assistant
`tool_calls` message.

DeepSeek and direct Xiaomi use `reasoning_content` directly. OpenRouter instead
returns plaintext reasoning as `message.reasoning` and documents
`reasoning_content` as an alias for `reasoning`. Live OpenRouter testing with
`xiaomi/mimo-v2.5` confirmed that responses can contain `message.reasoning`,
standard `message.tool_calls`, no `message.reasoning_content`, and a
`reasoning_details` array.

## Goals / Non-Goals

**Goals:**

- Preserve OpenRouter plaintext reasoning across tool follow-up turns.
- Reuse Deepy's existing `reasoning_content` replay mechanism.
- Keep OpenRouter behavior gated by OpenRouter base URL/provider context.
- Keep DeepSeek and direct Xiaomi replay behavior unchanged.
- Keep the change small enough to avoid forking or duplicating the SDK message
  conversion logic.

**Non-Goals:**

- Full `reasoning_details` preservation.
- Reordering, editing, or synthesizing OpenRouter reasoning blocks.
- Changing request-side OpenRouter `extra_body.reasoning` mapping.
- Changing UI, configuration, or provider selection behavior.

## Decisions

1. Alias OpenRouter plaintext reasoning into `reasoning_content`.

   Before the SDK converts a Chat Completions response into response output
   items, Deepy should detect OpenRouter responses whose assistant message has
   a non-empty `reasoning` string and no existing `reasoning_content`, then set
   `reasoning_content` to the same string. This lets the existing SDK
   `message_to_output_items` path produce a reasoning item without requiring
   `reasoning_details` support.

   Alternative considered: implement `reasoning_details` replay immediately.
   That preserves more structure but requires carrying raw provider-specific
   arrays through the SDK item model and restoring them exactly on the next
   assistant tool-call message. The current objective is smaller and aligns
   with OpenRouter's documented alias.

2. Extend the replay hook for OpenRouter only.

   Deepy's current replay hook returns true for DeepSeek and direct Xiaomi MiMo.
   The hook should also return true for OpenRouter Chat Completions contexts
   when the reasoning item originated from the same OpenRouter model or lacks
   provider metadata. The existing direct Xiaomi base URL gate should remain in
   place so Xiaomi-specific behavior does not bleed into OpenRouter and vice
   versa.

3. Keep `reasoning_details` out of scope.

   OpenRouter recommends `reasoning_details` for encrypted, summarized, or
   special reasoning blocks. Deepy should not discard or mutate any
   `reasoning_details` data that the SDK already preserves, but this change
   should not introduce a new storage/replay path for it. That can be handled
   later if a model requires full block preservation.

## Risks / Trade-offs

- [Risk] Some future OpenRouter models may require exact `reasoning_details`
  rather than plaintext alias replay. -> Mitigation: scope this change to
  plaintext `reasoning`; add a separate change for `reasoning_details` if live
  failures show it is required.
- [Risk] Replaying reasoning to a non-OpenRouter compatible endpoint could
  break a custom gateway. -> Mitigation: gate aliasing/replay by resolved
  OpenRouter base URL or provider identity.
- [Risk] The OpenAI Agents SDK may change its internal conversion behavior. ->
  Mitigation: cover the alias bridge with focused tests that exercise the SDK
  conversion path rather than only testing helper functions.
- [Risk] OpenRouter may return both `reasoning` and `reasoning_content`. ->
  Mitigation: preserve an existing `reasoning_content` value and only fill it
  when absent.

## Migration Plan

No user config migration is required. Rollback is to remove the OpenRouter alias
bridge and restore the replay hook to DeepSeek/direct Xiaomi only.

## Open Questions

- Should a later change add full `reasoning_details` replay for OpenRouter
  models that expose encrypted or provider-specific reasoning blocks?
