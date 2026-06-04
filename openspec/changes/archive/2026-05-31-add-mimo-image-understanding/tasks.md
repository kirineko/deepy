## 1. Capability And Data Model

- [x] 1.1 Add explicit image-input capability metadata to model catalog entries.
- [x] 1.2 Mark only `xiaomi` `mimo-v2.5` and OpenRouter `xiaomi/mimo-v2.5` as image-capable.
- [x] 1.3 Add helper APIs for checking whether the active settings support image input.
- [x] 1.4 Define a prompt image attachment data structure with label, MIME type, byte size, and data/ref fields.
- [x] 1.5 Add validation for supported image MIME types and maximum image size.

## 2. Model Input Construction

- [x] 2.1 Extend the runner input boundary so a user turn can carry prompt text plus image attachments.
- [x] 2.2 Convert supported image prompts to internal multipart content with text first and images after it.
- [x] 2.3 Normalize internal text/image content blocks to Chat Completions `text` and `image_url` parts.
- [x] 2.4 Ensure DeepSeek and non-image-capable OpenRouter custom models never receive image content blocks.
- [x] 2.5 Preserve text-only request shapes when no image attachments are present.
- [x] 2.6 Keep existing `Read` image follow-up messages compatible with the shared image normalization path.

## 3. Stable Terminal UI

- [x] 3.1 Add clipboard image paste detection to the prompt-toolkit input path without changing ordinary text paste behavior.
- [x] 3.2 Attach supported pasted images to the current prompt draft and render `[图片1]`, `[图片2]`, and later labels near the prompt.
- [x] 3.3 Reject unsupported image paste with a short non-blocking error while preserving prompt text and focus.
- [x] 3.4 Submit prompt text and attachments together as one user turn.
- [x] 3.5 Render submitted user turns with compact image labels and without raw base64.

## 4. Experimental Textual TUI

- [x] 4.1 Add clipboard image paste detection to `PromptTextArea` or its prompt panel integration.
- [x] 4.2 Attach supported pasted images to the Textual prompt draft and render compact image labels.
- [x] 4.3 Reject unsupported image paste with a short non-blocking error while preserving prompt text and focus.
- [x] 4.4 Submit Textual prompt text and attachments together as one user turn.
- [x] 4.5 Render Textual user transcript blocks with compact image labels and without raw base64.

## 5. Session And Display

- [x] 5.1 Persist user image turns with structured text and image content sufficient for resume.
- [x] 5.2 Redact raw base64/data URLs from session list titles and normal session display output.
- [x] 5.3 Preserve resumed image context for image-capable models.
- [x] 5.4 Detect resumed image context with a non-image-capable model and surface a concise incompatibility message before sending an unsupported request.
- [x] 5.5 Account for image content conservatively in local context estimates.

## 6. Tests And Validation

- [x] 6.1 Add unit tests for model image capability metadata and helper APIs.
- [x] 6.2 Add unit tests for multipart prompt conversion and Chat Completions normalization.
- [x] 6.3 Add regression tests proving DeepSeek and unsupported OpenRouter custom models do not receive image blocks.
- [x] 6.4 Add stable UI tests for supported paste, unsupported paste, text preservation, and image-label rendering.
- [x] 6.5 Add Textual TUI tests for supported paste, unsupported paste, text preservation, and image-label rendering.
- [x] 6.6 Add session tests for image persistence, resume behavior, and base64 redaction.
- [x] 6.7 Add compatibility tests for existing `Read` image follow-up messages.
- [x] 6.8 Run `openspec validate add-mimo-image-understanding --type change --strict`.
- [x] 6.9 Run focused tests for changed model/provider/session/UI surfaces.
- [x] 6.10 Run `uv run ruff check src tests`, `uv run ty check src`, and `uv run pytest` before marking implementation complete.
- [x] 6.11 Update prompt UIs so image labels render inside the input draft and deleting a label removes the corresponding attachment.
- [x] 6.12 Verify Xiaomi official image requests and remove `mimo-v2.5-pro` from direct Xiaomi image-capable metadata after API 404.
- [x] 6.13 Remove OpenRouter `xiaomi/mimo-v2.5-pro` from image-capable metadata for consistency with the MiMo Pro image-input boundary.
- [x] 6.14 Make unsupported-image paste visible in the transcript and ignore historical/session images for text-only models instead of blocking turns.
- [x] 6.15 Add a default image-understanding text part for image-only prompts so supported uploads do not trigger inferred tool actions.
- [x] 6.16 Treat prompt image labels as atomic editable units for Backspace/Delete in stable UI and Textual TUI.
