# Built-In Tools Specification

## Purpose

Deepy exposes a compact set of project tools to the model while preserving safe
file modification behavior and readable terminal output.
## Requirements
### Requirement: Core Tools

Deepy SHALL expose project tools for shell execution, local code search, v3 file
reading, v3 file writing, v3 exact text updates, user questions, web search, web
fetch, skill loading, and todo planning.

#### Scenario: Tools are registered

- **WHEN** the model agent is constructed
- **THEN** Deepy SHALL make the supported tools available through the OpenAI Agents
  SDK tool flow
- **AND** the registered tool set SHALL include `Search`, `Read`, `Write`, and
  `Update`
- **AND** the registered tool set SHALL identify `Search` as the preferred tool
  for local repository text/code searches
- **AND** the registered tool set SHALL identify `Update` as the primary exact
  text editing tool for one or more replacements across one or more files
- **AND** the registered tool set SHALL NOT include old model-facing file tools
  such as `read_file`, `edit_text`, `write_file`, `apply_patch`, `read`, or
  `modify`

### Requirement: Read-Before-Write Protection

Deepy SHALL protect existing files from stale or uninformed writes by ensuring
fresh runtime-managed read state or model-authored write state exists before
committing existing-file changes.

#### Scenario: Existing file is exact-updated without a prior read

- **WHEN** the model invokes `Update` for an existing file that has no
  runtime-managed read state in the current tool runtime
- **THEN** Deepy MAY internally establish managed read state from the current
  file contents before applying the update
- **AND** Deepy SHALL apply the update only if exact-match, uniqueness,
  expected-count, encoding, line-ending, and stale-write checks pass
- **AND** the successful result SHALL include metadata indicating that an
  internal auto-read was used

#### Scenario: Existing file is full-content replaced without a prior read

- **WHEN** the model invokes `Write` with content for an existing file without
  fresh runtime-managed read state
- **THEN** Deepy SHALL reject the operation
- **AND** Deepy SHALL direct the model to use `Read` before retrying the
  replacement

#### Scenario: Existing file changed after managed read state

- **WHEN** `Write` or `Update` attempts to mutate an existing file that already
  has managed read state
- **AND** the file has changed since that read state was recorded
- **THEN** Deepy SHALL reject the operation
- **AND** it SHALL require the file to be read again before editing

#### Scenario: File changes between planning and commit

- **WHEN** a managed text mutation reads or previews an existing file for a
  side-effecting operation
- **AND** the file changes before Deepy commits the mutation
- **THEN** Deepy SHALL reject the mutation before writing whenever the change is
  detectable through the managed read-state checks
- **AND** it SHALL return structured stale-read metadata

### Requirement: Unified File Modification Path

Deepy SHALL prefer the v3 `Update` tool for exact text changes so the model does
not repeatedly choose between overlapping write, edit, and patch tools.

#### Scenario: Model changes existing code

- **WHEN** the model needs to update existing code, tests, docs, or config
- **THEN** tool descriptions SHALL steer it toward `Update` for exact text
  replacements, including one edit, multiple edits in one file, and multiple
  edits across files
- **AND** tool descriptions SHALL steer it toward `Write` only for new files or
  explicit whole-file replacement
- **AND** tool descriptions SHALL steer it toward `Read` when context or fresh
  read state is needed before mutation

#### Scenario: Model exact-updates an existing file before reading it

- **WHEN** the model invokes `Update` for an existing file before invoking `Read`
- **THEN** Deepy MAY complete the update in the same tool call when internal
  read-state creation and exact update checks succeed
- **AND** Deepy SHALL NOT require a failed update result followed by a separate
  read call for this recoverable missing-read case

#### Scenario: Model exact-updates after a partial read

- **WHEN** the model has only partially read an existing file
- **AND** it invokes `Update` with a normal file-path exact edit
- **THEN** Deepy SHALL NOT require a failed update result followed by a separate
  full-file read when the current file is fresh and the exact update checks pass
- **AND** Deepy SHALL still reject stale partial read state before writing

#### Scenario: Model performs a multi-file update

- **WHEN** the model needs to update multiple files as one logical exact-text
  change
- **THEN** Deepy's tool guidance SHALL steer the model toward one `Update` call
  containing multiple edits
- **AND** successful results SHALL identify every changed file in structured
  metadata

### Requirement: Tool Output Display

Deepy SHALL render tool activity as concise progress and readable diffs for
managed file mutations.

#### Scenario: File content changes

- **WHEN** `Write` or `Update` succeeds
- **THEN** Deepy SHALL render a diff-style preview of changed content
- **AND** additions and deletions SHALL be visually distinguishable without
  relying only on leading `+` or `-` markers

#### Scenario: Update changes multiple files

- **WHEN** `Update` succeeds for multiple target files
- **THEN** Deepy SHALL render a concise changed-file summary
- **AND** its display diff preview SHALL include each changed file
- **AND** multi-file update diffs SHALL be rendered as separate per-file
  sections so each section can use its own file path for syntax highlighting
- **AND** detailed full diff metadata SHALL remain available for UI renderers

#### Scenario: Update call arguments are summarized

- **WHEN** Deepy renders a pending `Update` tool call with one or more edits
- **THEN** it SHALL summarize the call with the edit count, number of target
  files, and concise target file paths
- **AND** it SHALL NOT render full file contents, replacement blocks, or raw
  edit JSON as the tool-call argument summary

### Requirement: Web Research

Deepy SHALL provide self-owned web search and direct URL fetch tools instead of
depending on third-party DeepCode backends. WebSearch SHALL use a configured
SearXNG instance first when `tools.web_search.searxng_url` is set, and SHALL
fall back to DuckDuckGo when SearXNG is unreachable or returns an unusable
response. WebSearch SHALL use DuckDuckGo directly when no SearXNG URL is
configured.

#### Scenario: User asks for current online information

- **WHEN** the model invokes web search or fetch
- **THEN** Deepy SHALL use its own configured implementation
- **AND** a complete URL SHALL be fetchable through the web fetch tool

#### Scenario: SearXNG search succeeds

- **WHEN** the model invokes WebSearch and configured SearXNG returns usable results
- **THEN** Deepy SHALL return those results
- **AND** the tool metadata SHALL identify SearXNG as the successful provider

#### Scenario: SearXNG is unreachable and DuckDuckGo fallback succeeds

- **WHEN** the model invokes WebSearch and configured SearXNG fails because of timeout,
  DNS failure, connection failure, HTTP non-2xx, malformed response, parser
  failure, or empty results
- **AND** DuckDuckGo returns usable results
- **THEN** Deepy SHALL return the DuckDuckGo results
- **AND** the tool metadata SHALL identify DuckDuckGo and summarize the failed
  SearXNG attempt

#### Scenario: No SearXNG configured

- **WHEN** the model invokes WebSearch and no SearXNG URL is configured
- **THEN** Deepy SHALL use DuckDuckGo directly

#### Scenario: All search providers fail

- **WHEN** the model invokes WebSearch and every configured provider fails
- **THEN** Deepy SHALL return a structured tool failure
- **AND** the failure SHALL include concise, masked provider-attempt metadata
- **AND** the interactive session SHALL continue without an uncaught exception

### Requirement: WebFetch Readable HTML Extraction

Deepy SHALL return useful readable text from direct WebFetch calls for HTML
pages whose primary content is exposed through standard metadata when ordinary
body text extraction is empty or unusable.

#### Scenario: Metadata-backed HTML page is fetched

- **WHEN** the model invokes WebFetch for a complete HTTP or HTTPS URL
- **AND** the response is HTML
- **AND** ordinary body text extraction is empty or unusable
- **AND** the page contains standard description metadata
- **THEN** WebFetch SHALL include the metadata description in the readable output
- **AND** it SHALL preserve the final URL, title, content type, and structured
  metadata in the tool result

#### Scenario: Ordinary HTML body text is available

- **WHEN** the model invokes WebFetch for an HTML page with useful ordinary body
  text
- **THEN** WebFetch SHALL prefer the ordinary body text extraction
- **AND** it SHALL NOT replace that body text with metadata-only content

#### Scenario: Compressed direct fetch response is returned

- **WHEN** the model invokes WebFetch and the server returns a supported
  compressed response
- **THEN** WebFetch SHALL decode the response before charset decoding and HTML
  extraction
- **AND** it SHALL return a structured tool failure instead of an uncaught
  exception when the response uses an unsupported content encoding

### Requirement: Cross-Platform Shell Execution

Deepy SHALL execute model-requested shell commands using a wrapper compatible
with the detected command dialect while preserving the existing model-facing
shell tool contract.

#### Scenario: POSIX shell command is executed

- **WHEN** the active command dialect is `posix`
- **AND** the model invokes the shell execution tool
- **THEN** Deepy SHALL execute the command through a POSIX-compatible shell
- **AND** it SHALL preserve cwd changes between shell tool calls
- **AND** it SHALL return structured metadata including cwd, exit code, process
  id, shell path, shell kind, command dialect, and path style

#### Scenario: PowerShell command is executed

- **WHEN** the active command dialect is `powershell`
- **AND** the model invokes the shell execution tool
- **THEN** Deepy SHALL execute the command through PowerShell or PowerShell Core
- **AND** it SHALL preserve cwd changes between shell tool calls
- **AND** it SHALL capture a normalized integer exit code
- **AND** it SHALL return structured metadata including cwd, exit code, process
  id, shell path, shell kind, command dialect, and path style

#### Scenario: Shell command times out

- **WHEN** a shell command exceeds its timeout
- **THEN** Deepy SHALL terminate the running process
- **AND** it SHALL return a structured tool failure
- **AND** the failure metadata SHALL include cwd, timeout, process id, shell path,
  shell kind, command dialect, interrupted status, and output truncation status

### Requirement: Shell Tool Guidance

Deepy SHALL expose the model-facing shell execution tool as `shell` and describe
it as current-environment shell execution rather than bash-only execution.

#### Scenario: Tool documentation is loaded

- **WHEN** Deepy builds tool documentation for the model
- **THEN** the `shell` tool documentation SHALL state that commands must match the
  detected runtime shell and command dialect
- **AND** it SHALL mention PowerShell behavior for Windows PowerShell

#### Scenario: Function tools are registered

- **WHEN** Deepy registers function tools for the model
- **THEN** the registered shell execution tool SHALL be named `shell`
- **AND** the shell execution tool description SHALL avoid implying that every
  command runs in bash

### Requirement: AskUserQuestion Guidance

Deepy SHALL guide the model to use AskUserQuestion when clarification,
preferences, implementation choices, or required approval would materially
improve the result, while avoiding unnecessary questions for low-impact details.

#### Scenario: User intent is ambiguous

- **WHEN** the user's request has multiple plausible interpretations that would
  lead to materially different work
- **THEN** Deepy SHALL guide the model to use AskUserQuestion to clarify the
  intended direction before committing to a path

#### Scenario: Scope or preference affects implementation

- **WHEN** missing scope, preference, or trade-off information would
  significantly affect the implementation plan or user-facing outcome
- **THEN** Deepy SHALL guide the model to use AskUserQuestion before committing
  to a path

#### Scenario: Implementation choice affects the result

- **WHEN** multiple implementation approaches are plausible
- **AND** the choice would affect behavior, user experience, maintainability, or
  risk
- **THEN** Deepy SHALL guide the model to use AskUserQuestion to present a small
  set of clear options
- **AND** if one option is recommended, the recommended option SHALL be listed
  first and labeled as recommended

#### Scenario: Required approval is missing

- **WHEN** the next action needs user approval or a required decision
- **THEN** Deepy SHALL guide the model to use AskUserQuestion to pause and
  request that decision

#### Scenario: User language is Chinese

- **WHEN** the user's latest request is primarily Chinese
- **THEN** Deepy SHALL guide the model to ask AskUserQuestion questions and
  options in Chinese unless the user requested another language

#### Scenario: Detail is low impact

- **WHEN** a missing detail is low impact and Deepy can make a reasonable
  assumption
- **THEN** Deepy SHALL guide the model to proceed with the assumption instead of
  asking an unnecessary question

### Requirement: AskUserQuestion Display Safety

Deepy SHALL preserve the structured AskUserQuestion contract for model/runtime
communication while suppressing raw question payloads from normal user-facing
tool summaries.

#### Scenario: AskUserQuestion result is produced

- **WHEN** the AskUserQuestion tool returns a result
- **THEN** the result SHALL keep `awaitUserResponse=true`
- **AND** it SHALL keep `metadata.kind="ask_user_question"`
- **AND** it SHALL keep normalized question metadata for pending-question parsing

#### Scenario: AskUserQuestion call summary is formatted

- **WHEN** Deepy formats an AskUserQuestion call for terminal progress or history
  display
- **THEN** it SHALL NOT render the raw `questions` argument payload
- **AND** it SHALL render a concise label suitable for user-facing output

#### Scenario: Custom answer option is available

- **WHEN** Deepy presents an AskUserQuestion prompt to the user
- **THEN** the user SHALL have a clear custom-answer path in addition to model
  supplied options
- **AND** the custom-answer path SHALL NOT require the model to include an
  explicit custom-answer option in tool arguments

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

### Requirement: MCP Web Search Preference
Deepy SHALL prefer configured MCP web-search tools over built-in WebSearch while
preserving built-in WebSearch as a fallback.

#### Scenario: MCP web-search tool is active
- **WHEN** one or more active MCP tools are identified as web-search tools
- **THEN** Deepy's model instructions SHALL tell the model to prefer those MCP
  tools for web or current-information searches
- **AND** built-in WebSearch SHALL remain available as a fallback

#### Scenario: Tavily MCP server is active
- **WHEN** an active MCP server is explicitly configured with the `web_search`
  role or identified as a Tavily/search server
- **THEN** Deepy SHALL identify its search-capable MCP tools as preferred web
  search tools
- **AND** the model-facing guidance SHALL name those preferred MCP tools when
  possible

#### Scenario: Preferred MCP search fails during a turn
- **WHEN** a preferred MCP web-search tool fails, times out, or is unavailable
  during a model turn
- **THEN** the model MAY use built-in WebSearch to complete the search task
- **AND** Deepy SHALL keep the interactive session alive

#### Scenario: No MCP web-search tool is active
- **WHEN** MCP is disabled, no MCP web-search tools are active, or every MCP
  web-search server fails to connect
- **THEN** Deepy's built-in WebSearch SHALL keep its normal provider behavior
  using configured SearXNG and DuckDuckGo fallback

### Requirement: Todo Write Tool

Deepy SHALL expose a built-in `todo_write` tool for maintaining the active
session todo plan.

#### Scenario: Function tools are registered

- **WHEN** Deepy constructs the model agent
- **THEN** it SHALL register a `todo_write` FunctionTool through the OpenAI
  Agents SDK tool flow
- **AND** the tool schema SHALL accept a complete list of todo items containing
  `id`, `content`, and `status`

#### Scenario: Valid todo list is written

- **WHEN** the model invokes `todo_write` with a valid todo list
- **THEN** Deepy SHALL update the active session todo plan
- **AND** the tool result SHALL include structured metadata identifying the
  result as a todo-list update
- **AND** the tool result SHALL include enough metadata for the terminal UI to
  render the current board without parsing raw prose

#### Scenario: Todo list is read

- **WHEN** the model invokes `todo_write` without a `todos` list
- **THEN** Deepy MAY return the current todo plan without modifying it
- **AND** the read result SHALL NOT create a duplicate board update when the
  todo state has not changed

#### Scenario: Invalid todo list is rejected

- **WHEN** the model invokes `todo_write` with duplicate ids, empty content,
  unsupported statuses, or multiple `in_progress` items
- **THEN** Deepy SHALL return a structured tool failure
- **AND** it SHALL leave the previous valid todo plan unchanged

#### Scenario: Todo tool output is displayed

- **WHEN** Deepy formats a `todo_write` tool call or result for terminal output
- **THEN** it SHALL use the same normalized tool label convention as other
  built-in tools
- **AND** it SHALL NOT show raw todo JSON as the primary user-facing display

### Requirement: Textual Tool Result Surfaces
Deepy SHALL render built-in tool results in the experimental Textual TUI through
tool-specific readable surfaces while preserving existing model-facing tool
names and result JSON.

#### Scenario: Shell tool result is rendered in TUI
- **WHEN** the `shell` tool emits output in the experimental TUI
- **THEN** the TUI SHALL show command, cwd when known, exit code, status,
  duration when known, stdout, stderr, and truncation state in a shell-specific
  block
- **AND** failed, timed-out, or interrupted commands SHALL be visually
  distinguishable from successful commands

#### Scenario: Read tool result is rendered in TUI
- **WHEN** the `read` tool emits file content in the experimental TUI
- **THEN** the TUI SHALL show file path, line range or page range when known,
  and a readable preview
- **AND** large content SHALL be folded, truncated, or expanded through a
  deliberate interaction rather than dumped directly into the transcript

#### Scenario: Todo tool result is rendered in TUI
- **WHEN** the `todo_write` tool updates or reads todos in the experimental TUI
- **THEN** the TUI SHALL show a concise transcript summary
- **AND** it SHALL project the current todo list into a side panel or dedicated
  view when that surface is visible

#### Scenario: Web tool result is rendered in TUI
- **WHEN** `WebSearch` or `WebFetch` emits output in the experimental TUI
- **THEN** the TUI SHALL show source or URL metadata when available
- **AND** result bodies SHALL be expandable when they are too large for a
  concise transcript block

#### Scenario: MCP tool result is rendered in TUI
- **WHEN** an MCP-backed tool emits output or status metadata in the
  experimental TUI
- **THEN** the TUI SHALL identify the MCP server or tool when known
- **AND** it SHALL show success, failure, cleanup, or unavailable state without
  exposing raw internal tracebacks as the primary display

### Requirement: Textual Waiting-For-User Tool State
Deepy SHALL render tool results that require user input as an explicit waiting
state in the experimental Textual TUI.

#### Scenario: Tool result awaits user response
- **WHEN** a tool result contains `awaitUserResponse=true`
- **THEN** the TUI SHALL render the tool block as waiting for user input
- **AND** it SHALL expose the corresponding interactive surface when metadata
  identifies a supported waiting state

#### Scenario: AskUserQuestion awaits user response
- **WHEN** an AskUserQuestion result is rendered in the experimental TUI
- **THEN** the TUI SHALL show normalized questions and options
- **AND** it SHALL support a custom-answer path when provided by the question
  contract
- **AND** selected answers SHALL be visible in transcript history

### Requirement: Textual Tool Block Expansion
Deepy SHALL make large or detailed tool output expandable in the experimental
Textual TUI.

#### Scenario: Tool output has hidden details
- **WHEN** a TUI tool block contains details beyond its concise summary
- **THEN** the user SHALL be able to expand and collapse the block by keyboard
  and pointer interaction
- **AND** the expanded content SHALL remain within the tool block or a
  dedicated detail surface without overlapping transcript content

#### Scenario: Tool output is short and successful
- **WHEN** a successful tool output is short enough to read inline
- **THEN** the TUI MAY show the output directly in the concise block
- **AND** it SHALL still preserve a consistent title and status shape across
  tool types

### Requirement: File Tool Surface V2

Deepy SHALL expose a v2 model-facing file tool surface with explicit read, small
edit, whole-file write, and patch-oriented mutation intents.

#### Scenario: V2 file tools are registered

- **WHEN** Deepy constructs the model agent
- **THEN** it SHALL register `read_file`, `edit_text`, `write_file`, and
  `apply_patch` through the OpenAI Agents SDK tool flow
- **AND** the tool descriptions SHALL explain the intended edit scope of each
  tool

#### Scenario: Legacy aliases are not registered

- **WHEN** Deepy constructs the model agent
- **THEN** it SHALL NOT register old model-facing file tool aliases such as
  `read` or `modify`

#### Scenario: Tool intent is unambiguous

- **WHEN** the model needs to read a file, make a small exact edit, replace a
  whole file, or apply a structured multi-file change
- **THEN** Deepy's tool guidance SHALL steer it respectively toward `read_file`,
  `edit_text`, `write_file`, or `apply_patch`

### Requirement: Read File Tool

Deepy SHALL expose `read_file` for reading regular text files and recording
managed file snapshots.

#### Scenario: Text file is read

- **WHEN** the model invokes `read_file` for a regular supported text file
- **THEN** Deepy SHALL return readable text content and metadata
- **AND** it SHALL record a managed snapshot containing a snapshot id, mtime,
  size, content hash, encoding, and line-ending metadata

#### Scenario: Partial text file is read

- **WHEN** the model invokes `read_file` with a partial range or line limit
- **THEN** Deepy SHALL return snippet metadata that can be used by later
  `edit_text` operations
- **AND** it SHALL NOT treat the partial read as permission for an unrestricted
  whole-file replacement

#### Scenario: Non-text file is read

- **WHEN** the model invokes `read_file` for a non-text target that Deepy can
  describe but not safely text-edit
- **THEN** Deepy SHALL return metadata for the target when supported
- **AND** it SHALL mark the target as not tracked for text mutation

### Requirement: Path Resolution And Mutation Policy

Deepy SHALL resolve file mutation targets through a shared path resolver and
policy layer before reading or writing bytes.

#### Scenario: Path escapes the workspace

- **WHEN** a file mutation target resolves outside the allowed workspace or
  writable roots
- **THEN** Deepy SHALL reject the mutation before any side effect
- **AND** it SHALL return a structured path-policy error

#### Scenario: Symlink escapes the workspace

- **WHEN** a file mutation target is a symlink or contains symlink components
  that resolve outside the allowed mutation boundary
- **THEN** Deepy SHALL reject the mutation before any side effect
- **AND** it SHALL include symlink policy metadata in the result

#### Scenario: Target matches ignore or sensitive-file policy

- **WHEN** a file mutation target matches a configured ignore rule or
  sensitive-file rule
- **THEN** Deepy SHALL apply the configured policy as allow, warn, require
  approval, or deny
- **AND** the tool result metadata SHALL identify the policy decision

### Requirement: Approval And Guardrail Metadata Hooks

Deepy SHALL provide a pre-commit approval and guardrail hook for managed file
mutations without requiring an interactive approval UI in this change.

#### Scenario: Mutation is allowed by policy

- **WHEN** the approval and guardrail adapter returns `allow` for a managed file
  mutation
- **THEN** Deepy SHALL continue the mutation pipeline
- **AND** the successful tool result SHALL include policy metadata when relevant

#### Scenario: Mutation receives a warning by policy

- **WHEN** the approval and guardrail adapter returns `warn` for a managed file
  mutation
- **THEN** Deepy MAY continue the mutation pipeline
- **AND** the tool result SHALL include structured warning metadata

#### Scenario: Mutation requires future approval

- **WHEN** the approval and guardrail adapter returns `requires_approval`
- **THEN** Deepy SHALL NOT launch an interactive approval UI in this change
- **AND** it SHALL return a structured policy result or failure describing the
  pending approval requirement
- **AND** it SHALL NOT commit file side effects

#### Scenario: Mutation is denied by policy

- **WHEN** the approval and guardrail adapter returns `deny`
- **THEN** Deepy SHALL reject the mutation before any file side effect
- **AND** the structured error metadata SHALL include the guardrail or approval
  policy reason when safe to expose

### Requirement: Managed Text Mutation Engine

Deepy SHALL route all built-in text file mutation tools through a shared managed
text mutation engine.

#### Scenario: Text mutation is executed

- **WHEN** `edit_text`, `write_file`, or `apply_patch` performs a text file
  mutation
- **THEN** Deepy SHALL use shared path resolution, text decoding, snapshot,
  stale/hash checks, diff, and byte-writing behavior

#### Scenario: Non-text target is rejected

- **WHEN** a built-in text mutation tool targets a binary, image, video, PDF,
  notebook, archive, database, directory, device, socket, or other unsupported
  non-regular text target
- **THEN** Deepy SHALL reject the mutation
- **AND** it SHALL return a structured error explaining that the target cannot be
  safely mutated through text tools

#### Scenario: Parent directories are created after validation

- **WHEN** a managed text mutation needs to create parent directories
- **THEN** Deepy SHALL create those directories only after path, target, snapshot,
  and pre-write validation has passed
- **AND** rejected mutations SHALL NOT leave newly created empty parent
  directories behind

### Requirement: Structured File Mutation Errors

Deepy SHALL return structured error metadata for built-in file mutation failures.

#### Scenario: Mutation has no effect
- **WHEN** a built-in text mutation would produce the same bytes as the current
  file
- **THEN** Deepy SHALL return a structured no-op result according to the tool
  contract
- **AND** it SHALL NOT silently report a successful content change
- **AND** for mixed `Update` batches it SHALL report no-op edits as skipped while
  allowing other valid staged edits to commit

### Requirement: Atomic Managed Text Writes

Deepy SHALL write managed text mutations through an atomic or best-effort atomic
byte-writing path with backup support where policy requires it.

#### Scenario: Managed text file is written

- **WHEN** Deepy commits updated text bytes for a managed mutation
- **THEN** it SHALL write bytes to a temporary file in the target directory and
  rename it over the target when the platform supports that operation
- **AND** it SHALL preserve existing file permissions when possible

#### Scenario: Backup is requested by policy

- **WHEN** the managed mutation policy requires a backup for a target file
- **THEN** Deepy SHALL create backup metadata before committing the mutation
- **AND** the tool result SHALL include enough metadata to locate or describe the
  backup

#### Scenario: Windows rename is temporarily denied

- **WHEN** a Windows managed text write receives a retryable rename error such as
  `EPERM` or `EACCES`
- **THEN** Deepy SHALL retry the rename with a bounded backoff before failing

#### Scenario: Atomic write fallback is used

- **WHEN** Deepy cannot complete an atomic rename and must use a non-atomic
  fallback
- **THEN** the tool result metadata SHALL identify that fallback
- **AND** the mutation SHALL still use Deepy's selected byte encoding

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

### Requirement: Provider-Compatible Tool Schemas
Deepy SHALL expose built-in tool schemas in a provider-compatible form while
preserving the same built-in tool names and runtime semantics.

#### Scenario: MiMo receives a tool schema with nullable optional arguments
- **WHEN** Deepy constructs built-in tools for a MiMo-compatible model
- **AND** a tool schema has a property whose JSON schema type includes `null`
- **AND** that property appears in the schema's `required` list
- **THEN** the model-visible schema SHALL remove that property from `required`
- **AND** it SHALL remove `null` from that property's model-visible type while
  leaving the property available as optional in `properties`
- **AND** it SHALL preserve the tool name, description, strict mode, and
  invocation handler

#### Scenario: MiMo omits an optional nullable tool argument
- **WHEN** a MiMo-compatible model invokes a built-in tool without an optional
  nullable argument
- **THEN** Deepy SHALL interpret the missing argument using the same runtime
  default as an explicit `null`
- **AND** the tool SHALL execute through the normal OpenAI Agents SDK tool flow

#### Scenario: Non-MiMo provider receives built-in tools
- **WHEN** Deepy constructs built-in tools for DeepSeek or a non-MiMo provider
- **THEN** Deepy SHALL preserve the existing model-visible tool schemas
- **AND** it SHALL NOT remove nullable fields from `required`

#### Scenario: Nested schema contains nullable required fields
- **WHEN** a MiMo-compatible model receives a built-in tool schema with nested
  object schemas
- **THEN** Deepy SHALL apply the nullable-required compatibility transformation
  recursively to nested object schemas
- **AND** it SHALL preserve non-nullable required fields at every level

### Requirement: Recoverable Tool Argument Handling
Deepy SHALL conservatively recover high-confidence malformed built-in tool
arguments before returning an invalid-arguments tool failure.

#### Scenario: Unquoted snapshot id is repaired
- **WHEN** the model invokes a built-in file mutation tool with otherwise valid
  JSON-like arguments whose only parse failure is an unquoted `snapshot_<number>`
  value in a `snapshot_id` field
- **THEN** Deepy SHALL repair the value to a JSON string before invoking the tool
- **AND** it SHALL validate the repaired arguments against the tool schema before
  executing the tool
- **AND** the tool result metadata SHALL identify that argument repair was
  applied

#### Scenario: Unquoted snippet id is repaired
- **WHEN** the model invokes `edit_text` with otherwise valid JSON-like
  arguments whose only parse failure is an unquoted `snippet_<number>` value in
  a `snippet_id` field
- **THEN** Deepy SHALL repair the value to a JSON string before invoking
  `edit_text`
- **AND** it SHALL validate the repaired arguments against the tool schema before
  executing the tool

#### Scenario: Simple JSON-like literals are repaired
- **WHEN** a built-in tool receives otherwise valid JSON-like arguments
- **AND** the only malformed tokens are Python-style `None`, `True`, or `False`
  values or trailing commas
- **THEN** Deepy MAY repair those tokens to valid JSON equivalents
- **AND** it SHALL validate the repaired arguments before executing the tool

#### Scenario: Unsafe argument repair is rejected
- **WHEN** a built-in tool receives malformed arguments whose repair would require
  guessing string delimiters, escaping, nested structure, `content`,
  `old_string`, `new_string`, `old_text`, `new_text`, `anchor`, shell commands,
  or patch operation bodies
- **THEN** Deepy SHALL NOT execute the tool
- **AND** it SHALL return a structured invalid-arguments result
- **AND** the result metadata SHALL mark the failure as retryable when a valid
  retry can safely resolve it

### Requirement: Retryable Tool Failure Metadata

Deepy SHALL distinguish recoverable argument failures from unrecoverable tool
failures through structured metadata.

#### Scenario: Safety failures remain blocking
- **WHEN** a file mutation fails because of stale snapshots, missing freshness
  tokens for existing-file replacement, path policy, unsupported target type,
  approval policy, guardrails, absent matches, ambiguous matches, count
  mismatches, atomic write failure, backup failure, or partial commit
- **THEN** Deepy SHALL NOT mark the result as a repaired argument success
- **AND** it SHALL preserve the existing blocking failure semantics and metadata
  for that error class

### Requirement: Background Shell Execution
Deepy's shell tool SHALL support explicit background execution for long-running commands without changing the default foreground behavior.

#### Scenario: Model launches a foreground shell command
- **WHEN** the model invokes the shell tool without background execution enabled
- **THEN** Deepy SHALL execute the command through the existing foreground shell path
- **AND** it SHALL return command output only after the foreground command completes, fails, times out, or is interrupted

#### Scenario: Model launches a background shell command
- **WHEN** the model invokes the shell tool with background execution enabled
- **THEN** Deepy SHALL start the command as a managed background task
- **AND** it SHALL return promptly with a structured tool result containing the task id, command, cwd, status, and output inspection guidance
- **AND** it SHALL NOT wait for the command to finish before allowing the model turn to continue

#### Scenario: Background shell launch fails
- **WHEN** Deepy cannot launch a requested background shell command
- **THEN** the shell tool SHALL return a structured failure
- **AND** it SHALL NOT register a running background task for the failed launch

### Requirement: Background Task Management Tools
Deepy SHALL expose model-facing tools for listing, inspecting, and stopping managed background tasks.

#### Scenario: Model lists background tasks
- **WHEN** the model invokes the task listing tool
- **THEN** Deepy SHALL return running and recent terminal background tasks
- **AND** each listed task SHALL include id, status, description or command, cwd, start time, and terminal outcome when available

#### Scenario: Model reads background task output
- **WHEN** the model invokes the task output tool for an existing task id
- **THEN** Deepy SHALL return task status and a bounded output preview or tail
- **AND** it SHALL indicate whether the task is still running
- **AND** it SHALL indicate whether more output is available beyond the returned preview

#### Scenario: Model waits for task output
- **WHEN** the model invokes the task output tool with blocking enabled and a timeout
- **THEN** Deepy SHALL wait up to the requested timeout for the task to reach a terminal state
- **AND** it SHALL return the latest status and output when the task completes or the wait times out

#### Scenario: Model stops a background task
- **WHEN** the model invokes the task stop tool for a running task id
- **THEN** Deepy SHALL request termination for that task
- **AND** the tool result SHALL report the task id and current stop status

#### Scenario: Model manages an unknown task
- **WHEN** the model invokes a background task management tool with an unknown task id
- **THEN** Deepy SHALL return a structured "task not found" failure
- **AND** the interactive session SHALL continue without an uncaught exception

### Requirement: Constrained Test Shell

Deepy SHALL provide a constrained command execution tool for verification-focused
subagents.

#### Scenario: Test shell command requires approval

- **WHEN** `test_shell` receives a useful but medium-risk command such as
  direct Python or Python3 script/code execution, dependency installation,
  service startup, Docker Compose startup, Rust `cargo run`, Go `go run`, Node
  package scripts that run local code, Java Maven or Gradle application startup,
  or local database access that may affect local runtime state
- **THEN** Deepy SHALL NOT execute the command immediately unless the active
  audit policy has approved or auto-approved that command
- **AND** it SHALL surface the command through SDK audit approval when an audit
  policy is active and the audit mode requires command approval
- **AND** it SHALL return a structured `approval_required` result with the
  command, risk classification, and approval reason when no audit approval path
  is active

#### Scenario: Common verification tools are requested

- **WHEN** `test_shell` receives common verification commands for Python, uv,
  pip, Node.js package managers, Java Maven or Gradle, Spring Boot, Rust, Go,
  frontend build/test/lint/typecheck tools, curl, ping, mysql, Docker Compose,
  head, or tail
- **THEN** Deepy SHALL classify the command using a documented allow/approval/
  deny policy
- **AND** direct local-code execution SHALL be classified as medium-risk
  `approval_required` rather than hard-denied solely because the command is an
  application run command
- **AND** the policy SHALL support ordinary test and diagnostic workflows without
  granting raw arbitrary shell access

### Requirement: Subagent Tool Exposure

Deepy SHALL expose only policy-approved tools to subagents.

#### Scenario: Explore tools are exposed

- **WHEN** Deepy constructs the built-in `explore` subagent
- **THEN** it SHALL expose local search and file-read tools
- **AND** it MAY expose web fetch/search and search-class MCP tools
- **AND** it SHALL NOT expose source mutation tools by default

#### Scenario: Reviewer tools are exposed

- **WHEN** Deepy constructs the built-in `reviewer` subagent
- **THEN** it SHALL expose local search and file-read tools
- **AND** it SHALL NOT expose source mutation tools by default
- **AND** it SHALL NOT expose `test_shell` by default

#### Scenario: Tester tools are exposed

- **WHEN** Deepy constructs the built-in `tester` subagent
- **THEN** it SHALL expose local search, file-read, and `test_shell`
- **AND** it SHALL NOT expose source mutation tools by default
- **AND** it SHALL NOT expose the raw unrestricted `shell` tool by default

### Requirement: Test Shell Approval Escalation

Deepy SHALL route test-shell approval needs through the main user interaction
flow.

#### Scenario: Subagent needs command approval

- **WHEN** `test_shell` receives a command classified as `approval_required`
  inside a subagent run
- **THEN** Deepy SHALL surface the command and reason through the outer SDK audit
  approval flow when an audit policy is active and the audit mode requires
  command approval
- **AND** Deepy SHALL wait for the user's audit decision before executing the
  command

#### Scenario: User approves command

- **WHEN** the user approves a `test_shell` command through the outer audit flow
- **THEN** Deepy SHALL execute the approved command through the constrained
  `test_shell` path
- **AND** it SHALL NOT grant the subagent raw unrestricted shell access

#### Scenario: Audit mode auto-approves command

- **WHEN** `test_shell` receives a command classified as `approval_required`
- **AND** the active audit mode auto-approves command execution
- **THEN** Deepy SHALL execute the command through the constrained `test_shell`
  path without a separate in-band token retry
- **AND** hard-denied `test_shell` policy decisions SHALL remain denied

#### Scenario: User rejects command

- **WHEN** the user rejects a `test_shell` command approval request
- **THEN** Deepy SHALL NOT execute the command
- **AND** the subagent or main agent SHALL report the verification limitation
  clearly

#### Scenario: No audit approval path is active

- **WHEN** `test_shell` receives a command classified as `approval_required`
- **AND** Deepy has no active SDK audit policy for that invocation
- **THEN** Deepy MAY return a structured `approval_required` result with an
  approval token
- **AND** a retry using that token SHALL execute only the same command through
  the constrained `test_shell` path

### Requirement: Tool Progress Failure Details

Deepy SHALL surface the first structured tool preflight failure in concise
progress summaries.

#### Scenario: Update preflight fails with structured failures
- **WHEN** `Update` returns a preflight failure with `metadata.failures`
- **THEN** Deepy SHALL include the first failure's edit index, error code, and
  concise error text in the tool progress summary
- **AND** it SHALL keep the summary short enough for terminal status display

### Requirement: Built-In Tool Audit Enforcement

Deepy SHALL apply the active system audit mode to built-in tools that can create
external side effects.

#### Scenario: Managed text write is approval-gated

- **WHEN** the active audit mode requires text write approval
- **AND** the model invokes `Write` or `Update`
- **THEN** Deepy SHALL pause the SDK run for approval before invoking the
  managed text mutation
- **AND** the mutation SHALL NOT be committed unless the user approves the
  interrupted tool call

#### Scenario: Shell command is approval-gated

- **WHEN** the active audit mode requires command approval
- **AND** the model invokes `shell`
- **THEN** Deepy SHALL pause the SDK run for approval before starting the shell
  command
- **AND** this SHALL apply to both foreground commands and commands requested
  with `run_in_background`

#### Scenario: Test shell medium-risk command is approval-gated

- **WHEN** the active audit mode requires command approval
- **AND** a subagent invokes `test_shell` with a command classified as
  `approval_required`
- **THEN** Deepy SHALL pause the SDK run for approval before executing the
  constrained command
- **AND** the approval SHALL apply only to that `test_shell` command invocation

#### Scenario: Background task termination is approval-gated

- **WHEN** the active audit mode requires command approval
- **AND** the model invokes `task_stop`
- **THEN** Deepy SHALL pause the SDK run for approval before requesting task
  termination

#### Scenario: Read-only built-in tools remain ungated

- **WHEN** the model invokes `Search`, `Read`, `WebSearch`, `WebFetch`,
  `task_list`, or `task_output`
- **THEN** Deepy SHALL NOT require audit approval solely because of the active
  audit mode

#### Scenario: Session planning remains ungated

- **WHEN** the model invokes `todo_write`
- **THEN** Deepy SHALL NOT treat the session todo update as a managed text write
  for audit approval purposes

### Requirement: Approval Preview Metadata

Deepy SHALL provide enough information for approval UI surfaces to summarize
pending built-in tool approvals before execution.

#### Scenario: Text write approval is displayed

- **WHEN** a pending approval is for `Write` or `Update`
- **THEN** Deepy SHALL show the tool name and target path or paths
- **AND** Deepy SHALL show a concise diff or content-change preview when it can
  be computed before committing the mutation

#### Scenario: Shell approval is displayed

- **WHEN** a pending approval is for `shell`
- **THEN** Deepy SHALL show the exact command string
- **AND** it SHALL show the current working directory for the command

#### Scenario: Task stop approval is displayed

- **WHEN** a pending approval is for `task_stop`
- **THEN** Deepy SHALL show the target background task id

### Requirement: Read Tool Image Follow-Up Compatibility
Deepy's existing image follow-up messages from `Read` SHALL remain compatible with the shared image input contract.

#### Scenario: Read loads an image file
- **WHEN** the model invokes `Read` for a supported image file
- **THEN** Deepy SHALL return a structured follow-up message containing image content
- **AND** the image content SHALL use the same internal image attachment representation accepted by model input normalization

#### Scenario: Read image follow-up is converted for Chat Completions
- **WHEN** a `Read` image follow-up message is included in model input for a supported image model
- **THEN** Deepy SHALL convert it to the same Chat Completions image-url shape used for pasted prompt images
- **AND** it SHALL preserve the base64 data URL and MIME type

#### Scenario: Read image follow-up targets unsupported model
- **WHEN** a `Read` image follow-up message would be sent to a model that does not support image input
- **THEN** Deepy SHALL avoid sending image content blocks to that model
- **AND** it SHALL surface a concise model incompatibility error rather than sending an unsupported payload

