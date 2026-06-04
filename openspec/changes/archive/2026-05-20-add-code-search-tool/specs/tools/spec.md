## MODIFIED Requirements

### Requirement: Core Tools

Deepy SHALL expose project tools for shell execution, local code search, file
reading, small-scope text editing, explicit file writing, patch-oriented file
mutation, user questions, web search, web fetch, skill loading, and todo
planning.

#### Scenario: Tools are registered

- **WHEN** the model agent is constructed
- **THEN** Deepy SHALL make the supported tools available through the OpenAI Agents
  SDK tool flow
- **AND** the registered tool set SHALL include `Search`, `read_file`,
  `edit_text`, `write_file`, and `apply_patch`
- **AND** the registered tool set SHALL identify `Search` as the preferred tool
  for local repository text/code searches
- **AND** the registered tool set SHALL identify `apply_patch` as the primary
  complex editing tool
- **AND** the registered tool set SHALL NOT include old `read` or `modify` file
  aliases

## ADDED Requirements

### Requirement: Built-In Code Search

Deepy SHALL provide a built-in `Search` tool for local project text/code search
without requiring an external ripgrep, grep, Git Bash, WSL, or shell-specific
search executable.

#### Scenario: Literal repository search

- **WHEN** the model invokes `Search` with a query and no explicit mode
- **THEN** Deepy SHALL search for the query as a literal string
- **AND** it SHALL return matching project results without invoking a shell
  command or external `rg` executable

#### Scenario: Regex repository search

- **WHEN** the model invokes `Search` with regex mode
- **THEN** Deepy SHALL interpret the query as a regular expression
- **AND** it SHALL enforce regex timeout protection
- **AND** it SHALL return a structured tool failure when the pattern is invalid
  or times out without usable partial results

#### Scenario: Search is read-only

- **WHEN** the model invokes `Search`
- **THEN** Deepy SHALL NOT modify files
- **AND** Deepy SHALL NOT create managed write snapshots for matched files

### Requirement: Search Scope And Filtering

Deepy SHALL constrain `Search` to safe, relevant project files by default while
allowing the model to narrow search scope.

#### Scenario: Search path is inside the project

- **WHEN** the model invokes `Search` with a relative file or directory path
- **THEN** Deepy SHALL resolve that path under the current project
- **AND** it SHALL search only within that resolved path

#### Scenario: Search path escapes the project

- **WHEN** the model invokes `Search` with a path that resolves outside the
  current project
- **THEN** Deepy SHALL reject the search
- **AND** it SHALL return structured path policy metadata

#### Scenario: Ignored files are skipped by default

- **WHEN** the model invokes `Search` without `include_ignored`
- **THEN** Deepy SHALL respect gitignore-style ignore rules
- **AND** it SHALL skip known high-noise directories such as `.git`,
  `node_modules`, `.venv`, `__pycache__`, `build`, and `dist`

#### Scenario: Ignored files are explicitly included

- **WHEN** the model invokes `Search` with `include_ignored` enabled
- **THEN** Deepy SHALL include files ignored by gitignore-style rules
- **AND** it SHALL still skip sensitive files and unsafe traversal targets

#### Scenario: Search is filtered by glob

- **WHEN** the model invokes `Search` with a glob filter
- **THEN** Deepy SHALL only search files whose project-relative path matches the
  glob filter

### Requirement: Search Output Modes

Deepy SHALL provide token-aware output modes so models can search broadly before
reading specific files.

#### Scenario: Files output mode

- **WHEN** the model invokes `Search` with `output_mode` set to `files`
- **THEN** Deepy SHALL return matching project-relative file paths
- **AND** it SHALL NOT return matching line contents

#### Scenario: Content output mode

- **WHEN** the model invokes `Search` with `output_mode` set to `content`
- **THEN** Deepy SHALL return matching project-relative paths, line numbers, and
  matching line text
- **AND** it SHALL include requested context lines when context is configured

#### Scenario: Count output mode

- **WHEN** the model invokes `Search` with `output_mode` set to `count`
- **THEN** Deepy SHALL return per-file match counts and aggregate match totals

#### Scenario: Search output is paginated

- **WHEN** the number of matching entries exceeds the requested limit
- **THEN** Deepy SHALL return only the requested page of results
- **AND** it SHALL include metadata indicating truncation and the next offset
  needed to continue

### Requirement: Search Safety And Decoding

Deepy SHALL avoid unsafe or unusable search output while preserving useful text
search behavior across platforms.

#### Scenario: Binary file is encountered

- **WHEN** `Search` encounters a binary or unsupported non-text file
- **THEN** Deepy SHALL skip the file
- **AND** it SHALL record skipped-file metadata without returning binary content

#### Scenario: Large text file is encountered

- **WHEN** `Search` encounters a text file larger than the configured search
  scan limit
- **THEN** Deepy SHALL skip or partially scan the file according to the Search
  implementation limits
- **AND** it SHALL record truncation or skipped-file metadata

#### Scenario: Sensitive file is encountered

- **WHEN** `Search` encounters a sensitive file such as `.env`, `.netrc`, or a
  private key file
- **THEN** Deepy SHALL NOT return that file's contents
- **AND** it SHALL include a concise warning or metadata indicating that
  sensitive results were filtered

#### Scenario: Windows encoded text is searched

- **WHEN** `Search` scans text encoded as UTF-16LE, UTF-8 with BOM, UTF-8, or
  GB18030
- **THEN** Deepy SHALL decode the text consistently with Deepy's file-reading
  behavior
- **AND** it SHALL return line numbers and line text without newline translation
  side effects

### Requirement: Search Tool Display And Guidance

Deepy SHALL present `Search` activity concisely and guide the model to use it for
local repository search instead of shell search commands.

#### Scenario: Search call is displayed

- **WHEN** Deepy renders a pending or completed `Search` tool call
- **THEN** it SHALL display the tool label as `[Search]`
- **AND** it SHALL summarize the query, search path, and optional filter without
  rendering raw JSON arguments

#### Scenario: Search result metadata is returned

- **WHEN** `Search` completes successfully
- **THEN** Deepy SHALL include metadata for result count, matched file count,
  output mode, engine, truncation status, and next offset when applicable

#### Scenario: Model guidance is loaded

- **WHEN** Deepy builds model-facing tool documentation or system guidance
- **THEN** it SHALL instruct the model to prefer `Search` for local project
  text/code search
- **AND** it SHALL discourage using `shell` for ordinary `grep`, `find`, or `rg`
  repository searches
