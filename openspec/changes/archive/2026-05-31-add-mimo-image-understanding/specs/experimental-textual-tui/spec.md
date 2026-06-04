## ADDED Requirements

### Requirement: Textual TUI Image Paste Attachments
The experimental Textual TUI SHALL support the same image attachment contract as the stable terminal UI.

#### Scenario: User pastes image into supported Textual prompt
- **WHEN** the Textual TUI prompt has focus
- **AND** the user pastes clipboard image data with Ctrl+V
- **AND** the active model supports image input
- **THEN** the TUI SHALL attach the image to the current prompt draft
- **AND** it SHALL insert the attachment label into the prompt input text as `[图片1]`, `[图片2]`, or the next available image label
- **AND** it SHALL preserve existing prompt text and cursor-editing behavior

#### Scenario: User deletes image label from Textual prompt input
- **WHEN** a Textual TUI prompt draft contains an inserted image label
- **AND** the user deletes that label from the prompt text before submission
- **THEN** the TUI SHALL remove the corresponding image attachment from the draft
- **AND** it SHALL NOT send that image with the next prompt submission

#### Scenario: User deletes within image label from Textual prompt input
- **WHEN** a Textual TUI prompt draft contains an inserted image label
- **AND** the cursor is inside the label or immediately after the label
- **AND** the user presses Backspace
- **THEN** the TUI SHALL delete the entire image label as one unit
- **AND** it SHALL remove the corresponding image attachment from the draft
- **WHEN** the cursor is inside the label or immediately before the label
- **AND** the user presses Delete
- **THEN** the TUI SHALL delete the entire image label as one unit
- **AND** it SHALL remove the corresponding image attachment from the draft

#### Scenario: User pastes image into unsupported Textual prompt
- **WHEN** the Textual TUI prompt has focus
- **AND** the user pastes clipboard image data with Ctrl+V
- **AND** the active model does not support image input
- **THEN** the TUI SHALL append a concise assistant-visible message to the transcript
- **AND** it SHALL NOT show the rejection only in the status/footer bar
- **AND** it SHALL discard the pasted image
- **AND** it SHALL preserve the current prompt text
- **AND** it SHALL keep accepting text input

#### Scenario: User submits Textual prompt with images
- **WHEN** a Textual TUI prompt draft contains text and image attachments
- **AND** the user presses Enter
- **THEN** the TUI SHALL submit the text and image attachments as one user turn
- **AND** the displayed user transcript block SHALL include the prompt text and compact image labels
- **AND** it SHALL NOT display raw base64 data

#### Scenario: Textual prompt remains responsive after image rejection
- **WHEN** an image paste is rejected because the model, MIME type, size, or clipboard adapter is unsupported
- **THEN** the Textual TUI SHALL keep the prompt focused and editable
- **AND** it SHALL preserve the current prompt text
