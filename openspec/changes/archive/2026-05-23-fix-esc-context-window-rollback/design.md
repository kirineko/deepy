## Context

Deepy stores two different context-related values in the session index:

- `activeTokens`: an internal effective-history estimate used for compaction
  decisions.
- `latestContextWindowTokens`: a user-facing checkpoint for latest request
  Context Window occupancy, derived from provider usage when available.

The terminal footer intentionally reads `latestContextWindowTokens` first. The
reported issue occurs when an Esc interrupt happens soon after prompt
submission. The interrupted-turn reconciliation can call `pop_item()` to remove
only the newly persisted user input. `pop_item()` currently recalculates
`ContextTokenState` and writes `state.active_tokens` into
`latestContextWindowTokens`, which can replace a precise latest-request value
such as `118,835` with an internal cumulative estimate near `3,000,000`.

## Goals / Non-Goals

**Goals:**

- Preserve precise latest-request Context Window checkpoints across Esc-only
  prompt rollbacks.
- Keep internal active-token estimates available for compaction after rollback.
- Prevent the prompt footer from showing impossible Context Window values such
  as `ctx 3M/1M` when provider usage indicates the latest request was much
  smaller.

**Non-Goals:**

- Redesign context compaction policy.
- Change cumulative Token Usage reporting.
- Change Esc interruption semantics for turns that already have assistant or
  tool suffixes beyond fixing checkpoint metadata.
- Change provider usage normalization.

## Decisions

1. Preserve `latestContextWindowTokens` during ordinary item rollback.

   `pop_item()` should update `activeTokens`, pending-token metadata, and record
   counts after removing an item, but it should not overwrite
   `latestContextWindowTokens` with `activeTokens`. When the previous index has a
   latest Context Window checkpoint from provider usage, rollback should keep
   that checkpoint.

   Alternative considered: recompute latest Context Window from cumulative
   `usage` every time `pop_item()` runs. That works when request entries are
   present, but preserving the existing checkpoint better handles compacted
   sessions and unknown-provider cases without changing semantics.

2. Allow explicit history rewrites to reset the checkpoint.

   `replace_items()` and `clear_session()` are different from ordinary rollback:
   they intentionally rewrite the active history. They may continue to set
   `latestContextWindowTokens` from the replacement estimate or zero because the
   checkpoint semantics are reset by the rewrite.

   Alternative considered: never allow local estimates in
   `latestContextWindowTokens`. That would remove useful compaction feedback
   immediately after explicit rewrites where no newer provider usage exists.

3. Validate with existing checkpoint semantics coverage.

   The existing JSONL session tests already exercise history shortening through
   `pop_item()`. Updating the existing assertion is sufficient to encode the
   corrected semantic boundary: ordinary tail rollback may refresh internal
   active-token metadata, but must not reset the latest Context Window
   checkpoint from the active-token estimate.

## Risks / Trade-offs

- Preserving a stale latest checkpoint after deleting arbitrary older history
  could be misleading if `pop_item()` is used for non-interrupt manual editing.
  Mitigation: `pop_item()` is currently used for tail rollback; explicit rewrite
  APIs remain the path for semantic resets.
- A rollback can still change `activeTokens`, so auto-compaction decisions may
  differ from the footer. Mitigation: this separation is intentional: footer
  shows latest request occupancy, while compaction uses effective active
  pressure.
- Existing tests may assume `pop_item()` sets `latestContextWindowTokens` to the
  active estimate after history shortening. Mitigation: update those tests to
  distinguish ordinary rollback from explicit rewrite semantics.
