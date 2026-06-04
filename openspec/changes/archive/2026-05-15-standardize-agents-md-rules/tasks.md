## 1. Rule Loader

- [x] 1.1 Rename or refactor the current project-rule loader around canonical `AGENTS.md` instruction loading.
- [x] 1.2 Add git-root discovery that returns the nearest ancestor containing `.git`, falling back to the working directory when no git root exists.
- [x] 1.3 Load global Deepy instructions from `~/.deepy/AGENTS.md` when non-empty.
- [x] 1.4 Load project `AGENTS.md` files from git root to current working directory in root-to-leaf order.
- [x] 1.5 Skip empty files and unsupported filenames such as `agents.md`, `Agents.md`, `CLAUDE.md`, `.cursorrules`, and `.cursor/rules`.
- [x] 1.6 Add source annotations for every retained instruction block.
- [x] 1.7 Add a default merged instruction byte budget and leaf-first truncation so specific child instructions are preserved before parent/global instructions.

## 2. System Prompt Contract

- [x] 2.1 Update the system prompt section name and wording from generic project rules to `AGENTS.md` instructions.
- [x] 2.2 State precedence clearly: system/developer constraints, direct user instructions, child `AGENTS.md`, parent `AGENTS.md`, global `~/.deepy/AGENTS.md`.
- [x] 2.3 Instruct the model to check for more specific `AGENTS.md` files before editing subdirectory files outside the initially loaded path.
- [x] 2.4 Instruct the model to update applicable `AGENTS.md` guidance when it changes documented commands, workflows, structures, styles, or conventions.

## 3. Documentation

- [x] 3.1 Update `README.md` to document `~/.deepy/AGENTS.md` and hierarchical project `AGENTS.md` loading.
- [x] 3.2 Update `README.zh-CN.md` with the same behavior and precedence rules.
- [x] 3.3 Add a concise recommended `AGENTS.md` structure covering commands, architecture, style, verification, and boundaries.

## 4. Tests

- [x] 4.1 Add tests for loading non-empty `~/.deepy/AGENTS.md` and ignoring `~/.agents/AGENTS.md`.
- [x] 4.2 Add tests for git-root-to-cwd hierarchical project loading order.
- [x] 4.3 Add tests for no-git fallback loading only the working directory.
- [x] 4.4 Add tests for empty file skipping and unsupported filename rejection.
- [x] 4.5 Add tests for instruction budget enforcement and leaf-first preservation.
- [x] 4.6 Add tests that the system prompt includes the strengthened instruction contract and precedence text.

## 5. Verification

- [x] 5.1 Run focused prompt tests for the changed loader and system prompt behavior.
- [x] 5.2 Run the full test suite or the repository's standard verification command.
- [x] 5.3 Run `openspec validate standardize-agents-md-rules --strict`.

## 6. Init Command

- [x] 6.1 Add a focused `/init` repository-analysis prompt builder for creating or updating project root `AGENTS.md`.
- [x] 6.2 Add `/init` to built-in slash command completion and `/help`.
- [x] 6.3 Route `/init` through the normal interactive model run path, including transcript rendering, usage footer, and session context updates.
- [x] 6.4 Document `/init` in the English and Chinese command references.
- [x] 6.5 Add tests for slash command discovery, help output, prompt construction, and interactive `/init` routing.
- [x] 6.6 Re-run focused tests, full tests, type/lint checks, and strict OpenSpec validation.

## 7. Status Indicator

- [x] 7.1 Add a lightweight helper for detecting applicable non-empty AGENTS.md instructions.
- [x] 7.2 Show `AGENTS.md loaded` in the interactive footer when applicable instructions exist.
- [x] 7.3 Add tests for footer display with and without applicable AGENTS.md instructions.
- [x] 7.4 Re-run focused tests, full tests, type/lint checks, and strict OpenSpec validation.
