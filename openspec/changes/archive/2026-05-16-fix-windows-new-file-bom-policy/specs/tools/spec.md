## MODIFIED Requirements

### Requirement: Windows Editor-Readable Unicode File Creation

Deepy SHALL create new managed text files as plain UTF-8 without a signature on
all platforms, including Windows, while preserving detected encodings when
editing existing files.

#### Scenario: Windows new non-ASCII text file is created

- **WHEN** Deepy runs on Windows
- **AND** the model creates a new text file through the managed modify/write path
- **AND** the content contains non-ASCII Unicode text
- **THEN** Deepy SHALL write the file as plain UTF-8 without signature
- **AND** the file bytes SHALL NOT start with the UTF-8 signature bytes `EF BB BF`

#### Scenario: New source file with Unicode content is parser-safe

- **WHEN** Deepy creates a new source file through the managed modify/write path
- **AND** the content contains non-ASCII Unicode text
- **THEN** Deepy SHALL write the file as plain UTF-8 without signature
- **AND** source parsers that read the file as `utf-8` SHALL NOT receive U+FEFF as the first character

#### Scenario: Existing file encoding is not changed for editor compatibility

- **WHEN** Deepy edits an existing text file
- **THEN** Deepy SHALL preserve the file's detected encoding
- **AND** it SHALL NOT add or remove a UTF-8 signature solely because the edit occurs on Windows

#### Scenario: GBK PowerShell cat rendering is not guaranteed

- **WHEN** a user displays a UTF-8 file through a GBK-configured PowerShell or console output path
- **THEN** Deepy is NOT required to make that external `cat` rendering readable
- **AND** Deepy SHALL continue to prioritize correct file bytes and parser-safe project file encoding
