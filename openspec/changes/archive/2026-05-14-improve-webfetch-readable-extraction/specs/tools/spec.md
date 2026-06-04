## ADDED Requirements

### Requirement: WebFetch Readable HTML Extraction

Deepy SHALL return useful readable text from direct WebFetch calls for HTML
pages whose primary content is exposed through standard metadata when ordinary
body text extraction is empty or unusable.

#### Scenario: Metadata-backed HTML page is fetched

- **WHEN** the model invokes WebFetch for a complete HTTP or HTTPS URL
- **AND** the response is HTML
- **AND** ordinary body text extraction is empty or unusable
- **AND** the page contains standard description metadata
- **THEN** WebFetch SHALL include the metadata description in the readable output
- **AND** it SHALL preserve the final URL, title, content type, and structured
  metadata in the tool result

#### Scenario: Ordinary HTML body text is available

- **WHEN** the model invokes WebFetch for an HTML page with useful ordinary body
  text
- **THEN** WebFetch SHALL prefer the ordinary body text extraction
- **AND** it SHALL NOT replace that body text with metadata-only content

#### Scenario: Compressed direct fetch response is returned

- **WHEN** the model invokes WebFetch and the server returns a supported
  compressed response
- **THEN** WebFetch SHALL decode the response before charset decoding and HTML
  extraction
- **AND** it SHALL return a structured tool failure instead of an uncaught
  exception when the response uses an unsupported content encoding
