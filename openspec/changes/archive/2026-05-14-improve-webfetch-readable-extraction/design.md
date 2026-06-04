## Context

WebFetch currently validates a complete URL, performs a direct HTTP GET, decodes
the response using the response charset, and extracts readable HTML text with a
small `HTMLParser`-based parser. That parser captures the document title and
ordinary body text while skipping scripts, styles, noscript content, and SVG.

For pages such as `https://leetcode.cn/problems/two-sum/description/`, the HTTP
request succeeds and the title is available, but the body contains little
ordinary text. The useful problem statement is exposed through standard metadata
such as `meta[name=description]`, and also through framework hydration data.
Because WebFetch ignores metadata and skips script content, the tool returns
`[No readable text extracted.]` even though the page contains useful content in
the initial HTML.

WebSearch already has browser-like request headers and compressed body decoding.
WebFetch should use the same HTTP compatibility baseline without changing the
model-visible WebFetch schema.

## Goals / Non-Goals

**Goals:**

- Return useful readable text for metadata-backed HTML pages when ordinary body
  extraction is empty or too sparse.
- Preserve existing successful extraction for normal HTML pages and plain text
  responses.
- Decode compressed HTTP responses when WebFetch sends browser-style
  `Accept-Encoding` headers.
- Keep the WebFetch tool schema, result shape, timeout, and output truncation
  behavior stable.
- Cover the behavior with deterministic unit tests.

**Non-Goals:**

- Execute JavaScript or add browser automation to WebFetch.
- Add a new scraping service, remote parser, or heavyweight readability
  dependency.
- Parse every possible application-specific hydration format.
- Change WebSearch behavior as part of this change.

## Decisions

1. Use browser-like HTTP headers for WebFetch.

   WebFetch should reuse the same general browser header profile as WebSearch,
   adjusted for direct document fetching. Some sites vary content or compression
   behavior based on headers, and the existing WebSearch profile already covers
   language, gzip/deflate support, and navigation-style fetch metadata.

   Alternative considered: keep WebFetch's minimal headers. Rejected because it
   leaves WebFetch less compatible than WebSearch and makes behavior differ
   unnecessarily between search and direct fetch.

2. Decode compressed WebFetch responses through the shared HTTP body decoder.

   Once WebFetch advertises gzip/deflate support, it must inspect
   `Content-Encoding` and decode before charset decoding. The existing
   `_decode_http_body()` helper already implements this for WebSearch and should
   be reused or adapted so the two web tools do not diverge.

   Alternative considered: avoid `Accept-Encoding` to sidestep decompression.
   Rejected because browser-like compatibility and shared behavior are more
   valuable, and the decoder already exists.

3. Treat metadata descriptions as a fallback readable text source.

   The HTML parser should collect standard description metadata, including
   `meta[name=description]`, `meta[property=og:description]`, and
   `meta[name=twitter:description]`. WebFetch should use this text when ordinary
   body extraction is empty or below a small usefulness threshold.

   Alternative considered: always prepend metadata to body text. Rejected
   because metadata often duplicates the article lead or contains SEO summaries;
   adding it unconditionally can make normal pages noisier.

4. Defer framework hydration JSON extraction.

   Hydration data such as `__NEXT_DATA__` can contain the desired content, but it
   also contains large UI state, cached queries, user status, telemetry, and
   unrelated strings. This change should solve the observed LeetCode class using
   standard metadata first. Hydration extraction can be a later targeted change
   if metadata fallback is insufficient.

   Alternative considered: recursively extract strings from all JSON scripts.
   Rejected because it risks dumping unrelated application state into model
   context and is hard to test generically.

## Risks / Trade-offs

- Metadata can be shorter than the fully rendered page -> prefer body text when
  it is useful, and use metadata only as fallback.
- Some sites may return unsupported encodings such as Brotli -> keep the failure
  structured and avoid advertising encodings that are not supported.
- Description metadata can contain HTML entities or compact whitespace -> normalize
  whitespace and rely on existing HTML character reference handling.
- The usefulness threshold could hide short legitimate pages -> keep the
  threshold conservative and test both normal body extraction and fallback.

## Migration Plan

1. Add metadata collection to the HTML extraction helper.
2. Route WebFetch response decoding through the shared compressed-body decoder.
3. Update WebFetch request headers to match the browser-like compatibility
   baseline.
4. Add focused unit tests for metadata fallback, compressed response decoding,
   and preservation of existing HTML/plain text behavior.
5. No user migration is required; existing WebFetch calls keep the same input
   and output contract.

## Open Questions

- Should a later change add targeted extraction for known hydration formats when
  metadata is missing, or should that remain outside WebFetch's lightweight
  direct-fetch scope?
