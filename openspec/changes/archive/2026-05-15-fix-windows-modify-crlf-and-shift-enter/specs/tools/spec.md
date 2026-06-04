## ADDED Requirements

### Requirement: Line-Ending-Tolerant File Modification

Deepy SHALL match model-requested file modifications when the requested `old_string` differs from the target file only by line-ending representation, while preserving existing read-before-write, stale-write, encoding, and line-ending protections.

#### Scenario: CRLF file is modified with LF old string

- **WHEN** a file has CRLF line endings
- **AND** the model has read the file
- **AND** the model invokes the modification tool with a multiline `old_string` containing LF line endings for text that exists in the file with CRLF line endings
- **THEN** Deepy SHALL match and replace the requested text
- **AND** it SHALL write the file back with CRLF line endings
- **AND** it SHALL report metadata indicating the match used line-ending normalization

#### Scenario: Snippet-scoped CRLF edit uses LF old string

- **WHEN** a snippet was produced from a file with CRLF line endings
- **AND** the model invokes the modification tool with that `snippet_id`
- **AND** the provided multiline `old_string` contains LF line endings for text that exists in the snippet with CRLF line endings
- **THEN** Deepy SHALL match only within the snippet scope
- **AND** it SHALL preserve the existing duplicate-match behavior within that scope

#### Scenario: GBK-compatible CRLF file is modified

- **WHEN** a GBK-compatible file has CRLF line endings
- **AND** the model invokes the modification tool with decoded Unicode text and LF line endings from the read output
- **THEN** Deepy SHALL match and replace the requested text
- **AND** it SHALL write the file back using the detected GBK-compatible encoding
- **AND** it SHALL preserve CRLF line endings

#### Scenario: Unrelated old string still fails

- **WHEN** the model invokes the modification tool with an `old_string` that is absent even after line-ending normalization
- **THEN** Deepy SHALL return `old_string not found in file`
- **AND** it SHALL continue to include closest-match metadata when available

### Requirement: Byte-Preserving Text Writes

Deepy SHALL write managed text file content through explicit byte encoding so platform text-mode newline translation cannot alter normalized line endings.

#### Scenario: CRLF content is written on Windows

- **WHEN** Deepy writes text content whose normalized line endings are CRLF
- **THEN** the bytes on disk SHALL contain single CRLF sequences
- **AND** they SHALL NOT contain doubled CRCRLF sequences caused by platform newline translation

#### Scenario: Existing file encoding is preserved during edit

- **WHEN** Deepy edits an existing text file with a detected encoding
- **THEN** Deepy SHALL encode the updated content using that detected encoding
- **AND** it SHALL preserve the file's detected line-ending style

#### Scenario: POSIX text write behavior remains stable

- **WHEN** Deepy writes a text file on macOS or Linux
- **THEN** byte output SHALL match the normalized content for the selected encoding
- **AND** no Windows-specific newline conversion SHALL be applied

### Requirement: Windows Editor-Readable Unicode File Creation

Deepy SHALL create new Windows text files containing non-ASCII Unicode content in an encoding that Windows Notepad and common IDEs can reliably identify as UTF-8.

#### Scenario: Windows new non-ASCII text file is created

- **WHEN** Deepy runs on Windows
- **AND** the model creates a new text file through the managed modify/write path
- **AND** the content contains non-ASCII Unicode text
- **THEN** Deepy SHALL write the file as UTF-8 with signature
- **AND** Windows Notepad and common IDEs SHALL be able to identify and display the Unicode text correctly

#### Scenario: Existing file encoding is not changed for editor compatibility

- **WHEN** Deepy edits an existing text file
- **THEN** Deepy SHALL preserve the file's detected encoding
- **AND** it SHALL NOT add a UTF-8 signature solely because the edit occurs on Windows

#### Scenario: GBK PowerShell cat rendering is not guaranteed

- **WHEN** a user displays a UTF-8 file through a GBK-configured PowerShell or console output path
- **THEN** Deepy is NOT required to make that external `cat` rendering readable
- **AND** Deepy SHALL continue to prioritize correct file bytes and editor-readable encoding

### Requirement: Managed Full-File Recovery Guidance

Deepy SHALL keep file recovery after repeated modification failures inside managed file tools rather than encouraging shell deletion and shell-based Unicode file recreation.

#### Scenario: Repeated exact replacement attempts fail

- **WHEN** the model repeatedly receives `old_string not found in file` while editing a read file
- **THEN** Deepy's tool guidance SHALL steer the model to re-read and use a managed full-file replacement path when the intended complete content is known
- **AND** it SHALL discourage deleting the file and recreating it through shell here-strings

#### Scenario: Read file is deleted outside managed tools

- **WHEN** a file was read and then deleted outside Deepy's managed write path
- **AND** the model attempts to recreate it through `modify(content=...)`
- **THEN** Deepy SHALL preserve stale-write protection
- **AND** it SHALL return guidance that the model must re-read, use a managed replacement path before deletion, or ask the user before destructive recovery
