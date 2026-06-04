## Why

Successful `Write` and `Update` tool results currently render two adjacent lines
when a diff preview is available: a generic `ok` summary followed by a diff
header that already contains the operation, path, and line counts. The generic
summary adds little information and consumes terminal space.

## What Changes

- Hide the generic success summary line for successful `Write` and `Update`
  results when a diff preview is rendered.
- Keep the diff header and preview unchanged.
- Preserve summaries for failures, retryable results, and successful results
  without a diff preview.

## Impact

Terminal output for successful file mutations becomes more compact while keeping
the useful changed-file and diff information visible.
