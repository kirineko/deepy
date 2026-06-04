## 1. Completion Contract Tests

- [x] 1.1 Add unit tests for `@` fragment extraction, including plain `@`, scoped paths, whitespace termination, and embedded email-like `@` tokens.
- [x] 1.2 Add unit tests for top-level candidate discovery that include files, directories with trailing `/`, and ignored names.
- [x] 1.3 Add unit tests for scoped traversal under a typed directory fragment such as `@src/`.
- [x] 1.4 Add unit tests proving traversal rejects scopes that resolve outside the project root.
- [x] 1.5 Add unit tests for candidate ranking: basename prefix, basename substring, then weaker relative-path fuzzy matches.
- [x] 1.6 Add prompt integration tests proving slash command completion and file mention completion both remain available.

## 2. In-Process File Discovery

- [x] 2.1 Add a file mention discovery module or helper that uses only Python in-process filesystem APIs.
- [x] 2.2 Define common ignored names and patterns for VCS metadata, dependency directories, virtual environments, build outputs, and caches.
- [x] 2.3 Implement top-level discovery with deterministic ordering, ignored-entry filtering, directory trailing `/`, and candidate limits.
- [x] 2.4 Implement scoped deep discovery with root containment checks, no symlink following by default, unreadable-directory tolerance, ignored-entry pruning, and candidate limits.
- [x] 2.5 Add short-lived caching for top-level and scoped deep discovery so repeated completion requests during typing do not rescan unnecessarily.

## 3. File Mention Completer

- [x] 3.1 Implement a `prompt_toolkit` completer that activates only for valid `@` mention fragments.
- [x] 3.2 Stop returning candidates when the current fragment resolves to an existing file under the active project root.
- [x] 3.3 Filter and rank candidates from the in-process discovery helper using basename-first matching.
- [x] 3.4 Return completions that replace only the current `@` fragment and leave accepted mentions as editable prompt text.
- [x] 3.5 Keep paths relative to the active project root and normalize displayed separators to `/`.

## 4. Prompt Integration

- [x] 4.1 Replace the current single slash-command `WordCompleter` with a composed completer for slash commands and file mentions.
- [x] 4.2 Pass the active interactive project root into prompt session creation so file mentions resolve against the same root shown in the UI.
- [x] 4.3 Preserve existing multiline input, history, Enter, Ctrl+J, Ctrl+D, placeholder, toolbar, and theme behavior.
- [x] 4.4 Confirm Tab accepts the current selected completion through prompt-toolkit's default completion behavior.

## 5. Verification

- [x] 5.1 Run focused tests for prompt input and file mention completion.
- [x] 5.2 Run the full `uv run pytest` suite.
- [x] 5.3 Run `uv run ruff check`.
- [x] 5.4 Run `uv run pyright`.
- [x] 5.5 Run OpenSpec validation for `add-file-mention-completion`.
