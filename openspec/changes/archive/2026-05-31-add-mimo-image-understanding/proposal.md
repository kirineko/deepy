## Why

Users need to ask Deepy questions about screenshots and other local images without first saving them to disk or routing through a tool call. MiMo and OpenRouter's MiMo routes already expose an OpenAI-compatible image understanding shape, so Deepy can add a narrow first version while keeping unsupported providers non-disruptive.

## What Changes

- Add first-class prompt image attachments for the stable terminal UI and experimental Textual TUI.
- Support image understanding only for Xiaomi official `mimo-v2.5` and OpenRouter `xiaomi/mimo-v2.5`. Xiaomi official `mimo-v2.5-pro` and OpenRouter `xiaomi/mimo-v2.5-pro` remain text-capable but do not support image input in this change.
- Allow users to paste clipboard images with Ctrl+V, show attachments as `[图片1]`, `[图片2]`, and preserve normal text editing and submission.
- When the active model does not support image input, show a short non-blocking error, discard the pasted image, preserve existing prompt text, and keep accepting text input.
- Send supported image turns through a shared OpenAI-compatible multipart content contract instead of provider-specific prompt text.
- Keep DeepSeek image input disabled for this change and reserve the internal capability boundary for future Kimi K2.6 support.
- Preserve image attachments in local session history without rendering raw base64 data in normal transcript views.

## Capabilities

### New Capabilities
- `image-understanding-input`: User-facing and provider-facing contract for pasted image attachments, supported model gating, multipart message construction, and transcript/session handling.

### Modified Capabilities
- `configuration`: Model metadata must expose image-input capability only for the supported MiMo model ids.
- `deepseek-provider`: The shared OpenAI-compatible provider path must serialize image attachments only for supported MiMo routes and must not send image blocks to DeepSeek.
- `terminal-ui`: The stable terminal UI must support non-blocking image paste affordances and attachment labels.
- `experimental-textual-tui`: The Textual TUI must support the same image paste and attachment-label contract.
- `session-context`: Sessions must retain image-attachment turns safely while previews avoid raw base64 output.
- `tools`: Existing image follow-up messages from `Read` must align with the shared image content contract.

## Impact

- Affected code includes model capability metadata, prompt input state, clipboard paste handling, runner input construction, Chat Completions input sanitization/conversion, session persistence/previews, and transcript rendering in both UI paths.
- Tests should cover supported/unsupported model gating, paste behavior, multipart request shape, session preview redaction, and existing `Read` image follow-up compatibility.
- No new external runtime service is required. Clipboard image extraction may require platform-specific adapters, but unsupported or unavailable clipboard image reads must fail without blocking text input.
