# Design

## Write Recovery

`Update` already resolves a missing or partial snapshot by reading text metadata,
marking the file as read, and then running `check_writable(require_read=True)`.
`Write` should use the same pattern for explicit whole-file replacement:

1. Resolve policy and supported-text checks first.
2. If the target exists and `snapshot_status()` is `missing` or `partial`, read
   the current file metadata and mark it as fully read.
3. Run the existing `check_writable(require_read=True)` guard.
4. Preserve encoding and line-ending behavior from the current file metadata.

If a snapshot is `stale` or `deleted`, `check_writable` remains the source of
truth and the mutation is rejected before writing.

## Runtime Status

The renderer will track an `activity_state` separate from the cumulative stream
token estimate. Reasoning deltas set `Thinking`; tool calls set a normalized
tool name. MCP tool calls collapse to `MCP`, while built-in tools use the
existing display-name normalization without arguments.

The active model-turn status detail is assembled as:

```text
↓ 850 tokens · Write
```

and `_runtime_status_text()` places any detail before `esc to interrupt`, giving
the visible structure:

```text
⠋ time 7s · ↓ 850 tokens · Write · esc to interrupt
```

## Markdown Code Blocks

The existing lightweight Markdown renderer already splits fenced code blocks.
It will pad each code-block line to the terminal width so the configured code
block style spans the block, and it will avoid showing a literal `code <lang>`
line as ordinary content.
