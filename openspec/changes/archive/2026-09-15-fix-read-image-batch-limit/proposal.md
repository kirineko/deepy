## Why

Batch Read can report success with nine images, then abort the next Responses request at image normalization. Reject the oversized tool result before it enters conversation history so the model can recover.

## What Changes

- Return a recoverable Read error with no image attachments when a batch exceeds eight images.
- Keep valid image batches and mixed text/image batches working.
- Cover the limit and SDK tool-error recovery in focused tests and document the limit.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `image-understanding-input`: Validate Read image batches before returning attachments.

## Impact

Read tool results, image input specification, Read instructions, and bilingual README documentation.
