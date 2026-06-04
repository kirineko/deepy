## Context

Deepy currently accepts user prompts as plain text while the `Read` tool already has a narrow image path that can produce SDK-style image follow-up messages. MiMo and OpenRouter's MiMo routes expose OpenAI-compatible image input through multipart message content, and Kimi K2.6 uses a closely related shape that should not require a different internal abstraction later.

The first version should stay small: only Xiaomi official `mimo-v2.5` and OpenRouter `xiaomi/mimo-v2.5` support image input. Xiaomi official `mimo-v2.5-pro` returns image-input 404, and Deepy treats OpenRouter `xiaomi/mimo-v2.5-pro` as text-only for the same safety boundary. DeepSeek remains text-only. Unsupported image paste must be a local UI rejection, not a model-turn blocker.

## Goals / Non-Goals

**Goals:**
- Represent user image attachments separately from prompt text until model input construction.
- Gate image input by explicit model capability metadata.
- Let users paste clipboard images with Ctrl+V and see compact `[图片N]` labels.
- Convert supported image turns to OpenAI-compatible multipart content for the Agents SDK / Chat Completions path.
- Preserve session history and transcript previews without exposing raw base64 in normal UI surfaces.
- Keep the internal content-block boundary compatible with future Kimi K2.6 support.

**Non-Goals:**
- Support DeepSeek image input.
- Add Kimi as a selectable provider or model in this change.
- Support video, audio, PDF multimodal input, image generation, or remote image URL entry.
- Add drag-and-drop, file picker, or slash-command attachment management.
- Upload images to a remote file API before model calls.

## Decisions

### Use Explicit Model Capabilities

Add image input support as model metadata rather than inferring from provider names or URL hosts.

Supported set:
- `provider=xiaomi`, `model=mimo-v2.5`
- `provider=openrouter`, `model=xiaomi/mimo-v2.5`

Alternatives considered:
- Provider-wide enablement: rejected because OpenRouter can route arbitrary custom models and Xiaomi may expose non-image models.
- Runtime probing: rejected for first version because it adds network latency and ambiguous failure modes to interactive paste.

### Keep Attachments Out Of Prompt Text

Represent a user submission as text plus structured image attachments. UI labels such as `[图片1]` are display affordances only and must not be appended to the natural-language prompt.

Alternatives considered:
- Insert data URIs into the prompt text: rejected because it makes editing unusable, pollutes history, and can leak large base64 into logs and transcript views.
- Insert markdown image syntax: rejected because providers require structured image content, not markdown references.

### Convert Once At Model Input Boundary

Build a shared adapter that turns a text prompt plus image attachments into multipart content:

```json
[
  {"type": "input_text", "text": "..."},
  {"type": "input_image", "image_url": "data:image/png;base64,..."}
]
```

The Chat Completions conversion layer should normalize that to provider-compatible `text` and `image_url` content blocks when required by the SDK path. Text should precede image blocks for compatibility with OpenRouter guidance.
If the user submits only image attachments, Deepy should add a short default text part at the provider boundary so the model treats the turn as image understanding and does not infer a file-editing task from the screenshot alone.

Alternatives considered:
- Make each provider construct its own prompt payload: rejected because MiMo, OpenRouter, and future Kimi share the same semantic shape.
- Store provider-ready `image_url` blocks directly in UI state: rejected because UI state should not depend on the transport representation.

### Reject Unsupported Image Paste Locally

When image data exists on the clipboard but the active model lacks image support, the UI should show a concise error and discard only that pasted image. Existing prompt text remains editable and the user can still submit text.

Alternatives considered:
- Block prompt submission until the user changes models: rejected because the user may still want to send the text-only request.
- Attach the image and fail later in the provider: rejected because it creates delayed, harder-to-understand errors and risks sending unsupported payloads.

### Persist Safe Session Items

Session history should retain enough image information to replay or resume a supported image turn, while normal previews and transcript rendering show compact labels rather than raw data URIs. If a storage refactor is necessary, prefer a content-addressed local attachment store with session items containing metadata and references; otherwise redact data URIs in preview surfaces at minimum.

Alternatives considered:
- Store only labels and drop image bytes after sending: rejected because resumed sessions would not match the provider context.
- Print raw base64 in session views: rejected because it is unreadable and can leak large payloads.

## Risks / Trade-offs

- Clipboard image APIs differ across macOS, Linux, Windows, prompt-toolkit, and Textual -> Isolate clipboard reads behind a small adapter and test unsupported/unavailable clipboard paths as non-blocking failures.
- Base64 images can be large -> enforce configured MIME/size limits before attaching and avoid normal UI rendering of data URIs.
- OpenRouter custom models may support images but are not in the curated MiMo list -> keep first-version behavior explicit; users can request broader support later.
- Existing `Read` image follow-up messages use SDK content block names -> preserve compatibility and add normalization tests instead of rewriting that tool path wholesale.
- Session storage may grow quickly with pasted images -> include tests and documentation for redacted display; consider content-addressed storage if direct embedding proves too heavy.

## Migration Plan

No user data migration is required for existing text-only sessions. Existing sessions that already contain image content blocks from tool follow-up paths must remain readable and replay-safe. If a local attachment store is introduced, new pasted images can use it while old inline image blocks remain supported.

Rollback is straightforward: disable image capability metadata and UI paste attachment handling. Text input, model selection, and existing `Read` image behavior should continue to operate.

## Open Questions

- Should the first implementation store pasted image bytes inline in the session item or in a local content-addressed attachment store?
- Should the stable terminal UI support removing a pasted image before submission in the first version, or is clearing the prompt draft enough for the initial scope?
- Which clipboard image formats are reliably available through the chosen prompt-toolkit and Textual integration points on Windows terminals?
