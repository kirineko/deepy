## Why

WebFetch can successfully request pages such as LeetCode problem descriptions
but return `[No readable text extracted.]` because the useful page content is
published through metadata or JavaScript hydration rather than ordinary body
text. This makes direct URL fetching unreliable for modern SPA and Next.js
pages even when the HTTP request itself succeeds.

## What Changes

- Improve WebFetch HTML extraction so pages with sparse body text can still
  return useful readable content from standard metadata.
- Align WebFetch request handling with the browser-like HTTP behavior already
  used by WebSearch, including compressed response decoding where needed.
- Preserve the existing WebFetch tool schema and output shape while improving
  the extracted text.
- Add regression coverage for LeetCode-like HTML, compressed responses, and
  existing plain HTML/plain text behavior.
- Do not add JavaScript browser rendering or a new external scraping service.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `tools`: WebFetch direct URL fetching should return readable content for
  metadata-backed HTML pages when ordinary body text extraction is empty or
  unusable.

## Impact

- Affected code: WebFetch implementation, HTML extraction helpers, HTTP body
  decoding path, and tool metadata/tests.
- Affected user experience: direct URL fetches for modern content pages should
  provide useful text instead of an empty extraction message.
- No breaking CLI, config, or model-visible tool schema changes are expected.
