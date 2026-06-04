## ADDED Requirements

### Requirement: Windows-Compatible Shell Output Decoding

Deepy SHALL decode captured shell stdout and stderr with Windows-compatible
fallbacks while preserving the existing shell execution contract.

#### Scenario: Windows native command emits UTF-16 output

- **WHEN** the model invokes the shell execution tool
- **AND** the command writes valid UTF-16-style text to stdout or stderr
- **THEN** Deepy SHALL return readable Unicode text in the shell tool output
- **AND** it SHALL preserve cwd tracking, exit-code tracking, and shell metadata

#### Scenario: Windows native command emits GBK-compatible output

- **WHEN** the model invokes the shell execution tool
- **AND** the command writes bytes that are not valid UTF-8 but are valid
  GBK-compatible text
- **THEN** Deepy SHALL return readable Unicode text in the shell tool output
- **AND** it SHALL preserve stdout and stderr ordering behavior from the existing
  shell result flow

#### Scenario: Shell output decoding does not require user shell reconfiguration

- **WHEN** a shell command produces non-ASCII output on Windows
- **THEN** Deepy SHALL decode the captured output inside the shell tool
- **AND** it SHALL NOT require the user or model to run `chcp`, edit a PowerShell
  profile, or otherwise change global terminal configuration

#### Scenario: UTF-8 shell output remains UTF-8

- **WHEN** a shell command writes valid UTF-8 output on macOS, Linux, or Windows
- **THEN** Deepy SHALL continue to return that output as readable Unicode text
- **AND** it SHALL preserve existing output truncation behavior
