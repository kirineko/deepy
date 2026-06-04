## 1. Read Range Recovery

- [x] 1.1 Add focused tests for single-target `Read` with an unquoted inclusive line range such as `range: 80-120`.
- [x] 1.2 Add focused tests for batch `Read` where one or more `files` entries contain unquoted inclusive line ranges.
- [x] 1.3 Add focused tests that unsafe malformed `Read` arguments remain retryable invalid-argument results and do not execute.
- [x] 1.4 Update the `Read` tool description to show quoted `range` examples for both single-target and multi-target reads.
- [x] 1.5 Implement narrow argument repair for simple unquoted `Read` range fields and require normal schema validation before execution.

## 2. File Mention Fuzzy Search

- [x] 2.1 Add focused tests showing that a short non-empty `@` fragment can match nested files and directories.
- [x] 2.2 Add focused tests showing that bare `@` still returns only top-level candidates.
- [x] 2.3 Add focused tests showing ignored/generated/dependency directories remain excluded from short-fragment fuzzy results.
- [x] 2.4 Add focused tests showing basename-prefix ranking remains ahead of weaker relative-path fuzzy matches.
- [x] 2.5 Update file mention candidate selection so short non-empty fragments use bounded deep discovery while bare `@` stays top-level.

## 3. Integration And Validation

- [x] 3.1 Verify slash command completion and input suggestion precedence are not changed by file mention fuzzy search.
- [x] 3.2 Run focused tests for tools and prompt input behavior.
- [x] 3.3 Run scoped quality checks for touched files.
- [x] 3.4 Run `openspec validate improve-read-range-and-file-mention-fuzzy-search --type change --strict`.

## 4. Textual TUI Prompt Parity

- [x] 4.1 Add focused TUI tests showing short non-empty `@` fragments match nested files and directories.
- [x] 4.2 Add focused TUI tests showing bare `@` remains limited to top-level candidates.
- [x] 4.3 Add focused TUI tests showing Esc followed by Delete or Backspace within 2 seconds clears the full prompt draft.
- [x] 4.4 Update Textual prompt file mention candidate selection to use bounded deep discovery for short non-empty fragments.
- [x] 4.5 Implement Textual prompt Esc-then-delete full-draft clearing without changing ordinary Delete or Backspace behavior.
- [x] 4.6 Temporarily verify Esc-then-delete falls back to ordinary deletion after the 2 second window expires, then remove the release-blocking test case.
