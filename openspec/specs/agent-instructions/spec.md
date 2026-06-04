# agent-instructions Specification

## Purpose

Deepy loads, applies, and surfaces `AGENTS.md` instructions so projects and
Deepy users can define concise agent-facing guidance with predictable scope,
precedence, initialization, and terminal visibility.
## Requirements
### Requirement: Global Deepy Instructions

Deepy SHALL load global agent instructions from `~/.deepy/AGENTS.md` when that file exists and is non-empty.

#### Scenario: Global instructions exist

- **WHEN** Deepy builds the system prompt and `~/.deepy/AGENTS.md` exists with non-empty content
- **THEN** Deepy SHALL include that content in the agent-instruction block
- **AND** Deepy SHALL annotate the included content with its source path

#### Scenario: Global instructions are absent

- **WHEN** Deepy builds the system prompt and `~/.deepy/AGENTS.md` does not exist or is empty
- **THEN** Deepy SHALL continue without global instructions
- **AND** Deepy SHALL NOT treat the missing file as an error

#### Scenario: Shared agents path exists

- **WHEN** `~/.agents/AGENTS.md` exists
- **THEN** Deepy SHALL NOT load it as global Deepy instructions

### Requirement: Project AGENTS.md Discovery

Deepy SHALL discover project `AGENTS.md` files from the active git root to the current working directory.

#### Scenario: Git root is found

- **WHEN** Deepy builds the system prompt from a working directory inside a git repository
- **THEN** Deepy SHALL inspect each directory from the git root through the working directory
- **AND** Deepy SHALL include each non-empty `AGENTS.md` found along that path

#### Scenario: Git root is not found

- **WHEN** Deepy builds the system prompt from a working directory that is not inside a git repository
- **THEN** Deepy SHALL inspect only the working directory for `AGENTS.md`

#### Scenario: Nested instructions exist

- **WHEN** `AGENTS.md` files exist at the git root and in a nested directory on the path to the working directory
- **THEN** Deepy SHALL include the git root file before the nested file

#### Scenario: Empty project file exists

- **WHEN** an `AGENTS.md` file exists but has no non-whitespace content
- **THEN** Deepy SHALL skip that file

### Requirement: Canonical Instruction Filename

Deepy SHALL use uppercase `AGENTS.md` as the only supported project instruction filename.

#### Scenario: Lowercase agents file exists

- **WHEN** `agents.md` exists in a directory and `AGENTS.md` does not
- **THEN** Deepy SHALL NOT load `agents.md`

#### Scenario: Mixed-case agents file exists

- **WHEN** `Agents.md` exists in a directory and `AGENTS.md` does not
- **THEN** Deepy SHALL NOT load `Agents.md`

#### Scenario: Tool-specific instruction files exist

- **WHEN** `CLAUDE.md`, `.cursorrules`, `.cursor/rules`, or other tool-specific rule files exist
- **THEN** Deepy SHALL NOT load them through the `AGENTS.md` instruction loader

### Requirement: Instruction Precedence

Deepy SHALL order loaded instructions so broader instructions appear before more specific instructions.

#### Scenario: Global and project instructions exist

- **WHEN** global and project `AGENTS.md` instructions are both loaded
- **THEN** Deepy SHALL place global instructions before project instructions

#### Scenario: Parent and child instructions conflict

- **WHEN** parent and child `AGENTS.md` files both apply to the current working directory
- **THEN** Deepy SHALL place the parent file before the child file
- **AND** Deepy SHALL instruct the model that the child file takes precedence when the files conflict

#### Scenario: User instruction conflicts with loaded instructions

- **WHEN** a direct user instruction conflicts with loaded `AGENTS.md` content
- **THEN** Deepy SHALL instruct the model that the direct user instruction takes precedence unless higher-priority system, developer, or safety constraints apply

### Requirement: Instruction Budget

Deepy SHALL enforce a bounded byte budget for the merged `AGENTS.md` instruction block.

#### Scenario: Instructions fit the budget

- **WHEN** all discovered instruction files and their source annotations fit within the configured instruction budget
- **THEN** Deepy SHALL include the full content of every discovered non-empty file

#### Scenario: Instructions exceed the budget

- **WHEN** discovered instruction files exceed the instruction budget
- **THEN** Deepy SHALL preserve the most specific applicable project files before parent and global files
- **AND** the final merged instruction block SHALL NOT exceed the budget

#### Scenario: A parent file is truncated

- **WHEN** a parent or global instruction file must be truncated to fit the budget
- **THEN** Deepy SHALL still include source annotations for retained content
- **AND** Deepy SHALL NOT truncate a more specific child instruction file in favor of that parent or global file

### Requirement: System Prompt Instruction Contract

Deepy SHALL describe loaded `AGENTS.md` content as binding agent guidance within the normal instruction hierarchy.

#### Scenario: System prompt includes instructions

- **WHEN** Deepy builds a system prompt
- **THEN** the prompt SHALL explain that loaded `AGENTS.md` content contains project and Deepy-specific working instructions
- **AND** the prompt SHALL explain the precedence of global, parent, child, and direct user instructions

#### Scenario: Agent edits a subdirectory file

- **WHEN** the agent plans to edit a file in a subdirectory that may have additional `AGENTS.md` guidance outside the initially loaded path
- **THEN** the prompt SHALL instruct the agent to check for more specific `AGENTS.md` files before making the edit

#### Scenario: Agent changes documented conventions

- **WHEN** the agent modifies commands, workflows, structure, style rules, or conventions described by an applicable `AGENTS.md`
- **THEN** the prompt SHALL instruct the agent to update the corresponding `AGENTS.md` when the change makes that guidance stale

### Requirement: AGENTS.md Init Command

Deepy SHALL provide an interactive `/init` command that generates or updates the project root `AGENTS.md`.

#### Scenario: User runs init without an existing AGENTS.md

- **WHEN** a user runs `/init` in interactive mode and the project root has no `AGENTS.md`
- **THEN** Deepy SHALL run the model with a repository-analysis prompt
- **AND** the prompt SHALL instruct the agent to create `AGENTS.md` in the project root
- **AND** the prompt SHALL instruct the agent to base the file on the actual repository rather than generic assumptions

#### Scenario: User runs init with an existing AGENTS.md

- **WHEN** a user runs `/init` in interactive mode and the project root already has `AGENTS.md`
- **THEN** Deepy SHALL run the model with a repository-analysis prompt
- **AND** the prompt SHALL instruct the agent to read and update the existing file instead of ignoring it

#### Scenario: Init command is discoverable

- **WHEN** Deepy builds slash command completions or prints `/help`
- **THEN** `/init` SHALL be listed as a built-in command

#### Scenario: Init command prompt scope

- **WHEN** Deepy runs the `/init` model prompt
- **THEN** the prompt SHALL instruct the agent to modify only the project root `AGENTS.md` unless the user explicitly requested otherwise
- **AND** the prompt SHALL recommend concise sections for commands, architecture, style, verification, and boundaries

### Requirement: Instruction Status Indicator

Deepy SHALL show a compact terminal status indicator when AGENTS.md instructions apply to the current project.

#### Scenario: Applicable instructions exist

- **WHEN** Deepy builds the interactive status footer and global or project `AGENTS.md` instructions are non-empty and applicable
- **THEN** the footer SHALL include the exact compact indicator `[AGENTS.md]`
- **AND** the indicator SHALL preserve the exact case-sensitive filename `AGENTS.md`
- **AND** the footer SHALL NOT show the verbose indicator `AGENTS.md loaded`

#### Scenario: No applicable instructions exist

- **WHEN** Deepy builds the interactive status footer and no global or project `AGENTS.md` instructions are applicable
- **THEN** the footer SHALL NOT show the AGENTS.md rules indicator

### Requirement: Todo Tool Guidance

Deepy SHALL instruct the model when and how to use the `todo_write` tool.

#### Scenario: User request is complex

- **WHEN** the user's request requires multiple meaningful steps, touches
  multiple files, or includes several distinct deliverables
- **THEN** Deepy SHALL guide the model to create or update a todo plan with
  `todo_write`
- **AND** the guidance SHALL tell the model to mark the current task
  `in_progress` before working on it

#### Scenario: User request is simple

- **WHEN** the user's request is a simple question, a single obvious edit, or a
  task that does not benefit from progress tracking
- **THEN** Deepy SHALL guide the model to skip `todo_write`
- **AND** it SHALL proceed directly without creating todo noise

#### Scenario: Real progress is made

- **WHEN** the model completes a meaningful todo item or discovers a necessary
  new task
- **THEN** Deepy SHALL guide the model to update the complete todo list with
  `todo_write`
- **AND** it SHALL avoid repeatedly calling `todo_write` when no task state has
  changed

#### Scenario: Model is ready to finish

- **WHEN** the model is about to provide the final answer for a task that used
  todos
- **THEN** Deepy SHALL guide the model to reconcile the todo plan so completed
  work is marked `completed`
- **AND** any unfinished work SHALL be clearly represented in the final answer
  rather than silently left ambiguous

