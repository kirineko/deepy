## ADDED Requirements

### Requirement: Windows PowerShell UTF-8 Shell Compatibility

Deepy SHALL make shell execution in Windows PowerShell UTF-8-safe for Python child processes while preserving the existing shell execution contract on non-Windows platforms.

#### Scenario: PowerShell command runs Python with Unicode source or output

- **WHEN** the active command dialect is `powershell`
- **AND** the OS family is `windows`
- **AND** the model invokes the shell execution tool for a command that runs Python code containing non-ANSI Unicode text
- **THEN** Deepy SHALL provide UTF-8 Python child-process defaults for that shell invocation
- **AND** it SHALL keep cwd tracking, exit-code tracking, stdout/stderr capture, and shell metadata behavior intact

#### Scenario: POSIX shell command is not mutated by Windows encoding setup

- **WHEN** the active command dialect is `posix`
- **AND** the model invokes the shell execution tool
- **THEN** Deepy SHALL NOT add Windows-specific PowerShell output encoding setup to the command wrapper
- **AND** it SHALL preserve the existing POSIX command arguments and shell behavior

#### Scenario: User-provided Python encoding environment is present

- **WHEN** a Windows shell invocation already has Python encoding environment values provided by the parent environment
- **THEN** Deepy SHALL NOT overwrite those explicit values
- **AND** it SHALL still return the normal shell result structure

### Requirement: GBK-Compatible Text File Modification

Deepy SHALL decode, display, modify, and write back GBK-compatible text files without corrupting Unicode content or changing the file's detected encoding.

#### Scenario: GBK-compatible file is read

- **WHEN** the model invokes the read tool for a text file that is not valid UTF-8 but is valid GBK-compatible text
- **THEN** Deepy SHALL decode the file as a GBK-compatible encoding
- **AND** it SHALL return readable Unicode text in the tool output
- **AND** it SHALL include the detected encoding in file metadata

#### Scenario: GBK-compatible file is modified

- **WHEN** a GBK-compatible file has been read
- **AND** the model invokes the modification tool with an `old_string` containing decoded Unicode text from that file
- **THEN** Deepy SHALL match and replace the requested text
- **AND** it SHALL write the file back using the detected GBK-compatible encoding
- **AND** it SHALL preserve the existing read-before-write and stale-write protections

#### Scenario: Valid UTF-8 file remains UTF-8

- **WHEN** the model reads or modifies a valid UTF-8 text file on macOS, Linux, or Windows
- **THEN** Deepy SHALL continue to detect the file as UTF-8
- **AND** it SHALL NOT reclassify the file as GBK-compatible text
