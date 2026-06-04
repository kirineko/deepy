## 1. Regression Coverage

- [x] 1.1 Add a WebFetch unit test for LeetCode-like HTML where body text is empty but `meta[name=description]` contains useful page content.
- [x] 1.2 Add WebFetch unit coverage for `meta[property=og:description]` or `meta[name=twitter:description]` fallback precedence.
- [x] 1.3 Add a WebFetch unit test for gzip or deflate compressed direct fetch responses.
- [x] 1.4 Add a WebFetch unit test that ordinary HTML body text remains preferred over metadata fallback.
- [x] 1.5 Add a WebFetch unit test that unsupported content encoding returns a structured tool failure.

## 2. HTML Extraction

- [x] 2.1 Extend the readable HTML parser to collect normalized standard description metadata.
- [x] 2.2 Update `_extract_readable_html()` to return title, body text, and metadata fallback text without changing callers unnecessarily.
- [x] 2.3 Add conservative fallback selection so metadata is used only when ordinary body extraction is empty or unusable.
- [x] 2.4 Preserve script/style skipping so JavaScript payloads are not dumped into readable output.

## 3. WebFetch HTTP Handling

- [x] 3.1 Update WebFetch request headers to use the browser-like compatibility baseline shared with WebSearch.
- [x] 3.2 Route WebFetch response decoding through the shared gzip/deflate-aware body decoder.
- [x] 3.3 Preserve existing WebFetch output fields and metadata, including final URL, content type, charset, byte count, truncation flags, and activity label.
- [x] 3.4 Keep unsupported content encoding errors inside the structured WebFetch error result path.

## 4. Documentation And Verification

- [x] 4.1 Update WebFetch tool documentation if needed to mention readable HTML extraction from metadata-backed pages.
- [x] 4.2 Run focused tool tests for WebFetch behavior.
- [x] 4.3 Run the broader relevant test suite for tools and prompt/tool documentation.
- [x] 4.4 Manually verify the LeetCode two-sum URL returns readable problem text instead of `[No readable text extracted.]`.
