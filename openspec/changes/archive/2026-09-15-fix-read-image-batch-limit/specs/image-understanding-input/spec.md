## ADDED Requirements

### Requirement: Recoverable Read Image Batch Validation
Deepy SHALL validate the aggregate image count of a batch Read result before returning image attachments to the agent.

#### Scenario: Read batch exceeds the image limit
- **WHEN** a batch Read produces more than eight images
- **THEN** Read SHALL return an error explaining the limit and asking for a smaller batch
- **AND** the error SHALL contain no image attachments
- **AND** the agent SHALL be able to receive the tool error and continue with a smaller Read request

#### Scenario: Read batch is within the image limit
- **WHEN** a batch Read produces at most eight images with optional text targets
- **THEN** Deepy SHALL preserve the successful image attachments and text results in target order
- **AND** text targets SHALL NOT count toward the image limit
