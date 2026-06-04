## ADDED Requirements

### Requirement: Stable UI Image Paste Attachments
Deepy SHALL support non-blocking clipboard image paste handling in the stable prompt-toolkit terminal UI.

#### Scenario: User pastes image into supported model prompt
- **WHEN** the stable terminal UI is focused on the prompt
- **AND** the user pastes clipboard image data with Ctrl+V
- **AND** the active model supports image input
- **THEN** Deepy SHALL attach the image to the current prompt draft
- **AND** it SHALL insert the attachment label into the prompt input text as `[图片1]`, `[图片2]`, or the next available image label
- **AND** it SHALL preserve existing prompt text and cursor-editing behavior

#### Scenario: User deletes image label from prompt input
- **WHEN** a stable terminal UI prompt draft contains an inserted image label
- **AND** the user deletes that label from the prompt text before submission
- **THEN** Deepy SHALL remove the corresponding image attachment from the draft
- **AND** it SHALL NOT send that image with the next prompt submission

#### Scenario: User deletes within image label from prompt input
- **WHEN** a stable terminal UI prompt draft contains an inserted image label
- **AND** the cursor is inside the label or immediately after the label
- **AND** the user presses Backspace
- **THEN** Deepy SHALL delete the entire image label as one unit
- **AND** it SHALL remove the corresponding image attachment from the draft
- **WHEN** the cursor is inside the label or immediately before the label
- **AND** the user presses Delete
- **THEN** Deepy SHALL delete the entire image label as one unit
- **AND** it SHALL remove the corresponding image attachment from the draft

#### Scenario: User pastes image into unsupported model prompt
- **WHEN** the stable terminal UI is focused on the prompt
- **AND** the user pastes clipboard image data with Ctrl+V
- **AND** the active model does not support image input
- **THEN** Deepy SHALL append a concise assistant-visible message to the transcript
- **AND** it SHALL NOT show the rejection only in the status/footer bar
- **AND** it SHALL discard the pasted image
- **AND** it SHALL preserve the current prompt text
- **AND** it SHALL keep accepting text input

#### Scenario: User submits prompt with images
- **WHEN** a stable terminal UI prompt draft contains text and image attachments
- **AND** the user presses Enter
- **THEN** Deepy SHALL submit the text and image attachments as one user turn
- **AND** the displayed user transcript block SHALL include the prompt text and compact image labels
- **AND** it SHALL NOT display raw base64 data

#### Scenario: User inserts newline with image attachments
- **WHEN** a stable terminal UI prompt draft contains image attachments
- **AND** the user presses Ctrl+J
- **THEN** Deepy SHALL insert a newline into the prompt text
- **AND** it SHALL NOT submit the prompt
- **AND** it SHALL NOT remove the image attachments

#### Scenario: User pastes text
- **WHEN** the stable terminal UI receives pasted text without clipboard image data
- **THEN** Deepy SHALL preserve the existing text paste behavior
- **AND** it SHALL NOT create image attachments
