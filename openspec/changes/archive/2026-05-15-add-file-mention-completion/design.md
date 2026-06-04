## Context

Deepy's interactive prompt is implemented with `prompt_toolkit` in
`src/deepy/ui/prompt_input.py`. It already enables multiline input, history,
slash command completion, and custom key bindings. The current completer is a
single `WordCompleter` for slash command labels, so adding file mentions should
extend the existing completion path instead of replacing the prompt UI.

The requested behavior is similar to Kimi CLI's local file mention completer,
but Deepy must not rely on external system binaries. Many user machines will
not have `rg`, `fd`, or a working `git` command available, and Windows support
should not depend on Unix shell behavior. File discovery therefore needs to be
implemented in process using Python and prompt-toolkit only.

## Goals / Non-Goals

**Goals:**

- Trigger file and directory mention completion when the user types an
  appropriate `@` token.
- Keep existing slash command completion working.
- Support Tab acceptance through prompt-toolkit's normal completion flow.
- Discover candidates with an in-process, cross-platform implementation.
- Keep completion responsive through bounded traversal, caching, and scoped
  search.
- Avoid noisy candidates from dependency, cache, build, VCS, and virtual
  environment directories.
- Handle relative paths safely under the active project root.
- Add focused unit coverage for parsing, discovery, ranking, filtering, and
  prompt integration.

**Non-Goals:**

- Adding a Rust extension, native binary, or dependency on Rust crates.
- Depending on external commands such as `rg`, `fd`, `find`, or `git`.
- Parsing file contents or adding selected file content to the model context in
  this change.
- Supporting line ranges such as `@src/app.py:10-20`.
- Supporting quoted or escaped mention syntax for paths containing whitespace.
- Replacing prompt-toolkit or rebuilding the prompt UI.

## Decisions

1. Compose completers instead of replacing slash completion.

   The prompt session should use `prompt_toolkit.completion.merge_completers`
   or an equivalent small custom dispatcher to combine slash command completion
   and file mention completion. Slash completion remains scoped to `/` command
   tokens; file mention completion is scoped to the current `@` fragment.

   Alternative considered: replace the slash `WordCompleter` with a single
   custom completer handling every mode. Rejected because composition keeps the
   change smaller and preserves current slash behavior.

2. Implement file discovery in process with Python standard library traversal.

   Candidate discovery should use `Path.iterdir()` for top-level completion and
   `os.walk()` or `Path.rglob()` style traversal for deeper searches. The
   implementation must not shell out to `git`, `rg`, `fd`, or platform-specific
   commands. It may read project files such as `.gitignore` in the future, but
   the first implementation should rely on a conservative built-in ignore list
   rather than a full gitignore parser.

   Alternative considered: call `rg --files`, `fd`, or `git ls-files`.
   Rejected because the user explicitly wants no system-tool dependency and
   those tools are not guaranteed on end-user machines.

3. Use two discovery modes: top-level first, scoped deep search later.

   When the fragment is empty or short and contains no slash, completion should
   list only top-level entries. Once the fragment contains `/`, traversal starts
   at the already typed directory scope. Once the fragment is long enough,
   traversal can search the project tree for basename and relative-path matches.
   This prevents the first `@` keystroke from scanning a large repository.

   Alternative considered: build a full repository index at prompt startup.
   Rejected because startup should stay fast and the prompt should not pay
   indexing cost unless the user actually asks for file mentions.

4. Rank basename matches ahead of cross-path fuzzy matches.

   Users usually type the file or directory name they remember, not every parent
   directory segment. Ranking should prefer basename prefix matches, then
   basename substring matches, then relative-path fuzzy matches. Directories
   keep a trailing `/` so users can continue narrowing inside them.

   Alternative considered: rely only on prompt-toolkit's `FuzzyCompleter`
   ordering. Rejected because Kimi's regression coverage shows basename-first
   ranking produces better file mention results for coding projects.

5. Treat safety and portability as part of the completion contract.

   All returned candidates must be relative paths under the active project root.
   Scoped traversal must resolve paths and reject any path that escapes the
   project root. Traversal must not follow symlinks by default, and errors from
   unreadable directories should be ignored without breaking prompt input.

   Alternative considered: let `Path` operations raise and rely on the prompt
   to recover. Rejected because completion runs during typing and must never
   make the input prompt brittle.

6. Keep whitespace paths out of scope for the first implementation.

   The trigger parser should stop file mention completion once the fragment
   contains whitespace. Existing files with spaces are not completed unless a
   later change adds quoting or escaping. This keeps mention parsing predictable
   in natural-language prompts.

   Alternative considered: support shell-style escaping immediately. Rejected
   because it complicates insertion, cursor replacement, and tests without
   being required for the first usable version.

## Risks / Trade-offs

- Large repositories can still be expensive to walk -> Bound candidate count,
  use short-lived caches, search scoped subtrees first, and avoid deep traversal
  for empty or very short fragments.
- Built-in ignore rules will not exactly match `.gitignore` -> Start with common
  generated and dependency directories; leave full gitignore semantics for a
  future in-process parser if users need it.
- Prompt-toolkit completion can block if discovery is slow -> Keep traversal
  bounded and consider `ThreadedCompleter` or `complete_in_thread=True` during
  implementation if tests or manual checks show visible latency.
- Paths with whitespace will not complete -> Document the limitation in tests
  and keep parsing conservative until quoted mentions are designed.
- Symlinked directories may hide useful files -> Do not follow symlinks by
  default to avoid cycles and root escape surprises; users can still type paths
  manually.
