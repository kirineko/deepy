## Context

Deepy currently injects project rules through `src/deepy/prompts/rules.py` and `src/deepy/prompts/system.py`. The loader is intentionally small but incomplete: it reads only `project_root / "AGENTS.md"` and `~/.deepy/AGENTS.md`, joins them in a fixed order, and does not define directory scope, precedence, or context budget behavior.

The target model is a simple `AGENTS.md` instruction system, not a Cursor-style rule engine. Project files use the shared `AGENTS.md` name so repositories can define agent-facing guidance in a predictable place. Deepy-specific global guidance remains under `~/.deepy/AGENTS.md` because it belongs to Deepy's local configuration domain, unlike Agent Skills which intentionally live under the cross-agent `.agents/skills` layout.

## Goals / Non-Goals

**Goals:**

- Load Deepy global guidance from `~/.deepy/AGENTS.md`.
- Load project guidance from `AGENTS.md` files along the path from git root to the current working directory.
- Preserve clear precedence: global first, then project root to cwd, with later and more specific files taking precedence.
- Make loaded instructions auditable by preserving source annotations.
- Bound total loaded instruction size while protecting the most specific files from truncation.
- Strengthen system prompt language so loaded instructions are treated as binding guidance within the normal instruction hierarchy.
- Keep implementation dependency-free and testable.

**Non-Goals:**

- No compatibility with `.agents/AGENTS.md`, `~/.agents/AGENTS.md`, `agents.md`, `.deepy/rules`, `.cursor/rules`, `CLAUDE.md`, or other fallback names.
- No `AGENTS.override.md` support in this change.
- No Cursor `.mdc` metadata, glob-triggered rules, rule marketplace, or manual rule invocation.
- No runtime file-watcher; instructions are loaded when the system prompt is built for the session/run.

## Decisions

### Use `~/.deepy/AGENTS.md` for global Deepy instructions

Global instructions describe the user's Deepy-specific working agreements, not a cross-agent skill package. Keeping the file under `~/.deepy` matches Deepy's existing config and session state boundary and avoids polluting the shared `.agents` namespace.

Alternative considered: `~/.agents/AGENTS.md`. This aligns superficially with Agent Skills, but `AGENTS.md` global behavior is agent-specific across existing tools. Skills are portable capability packages; global rules are product/runtime preferences.

### Use only uppercase `AGENTS.md`

The canonical project file name is `AGENTS.md`. Supporting additional casings or fallback names would reduce migration friction, but this feature has not been formally adopted and the user explicitly prefers a clean standardization.

Alternative considered: support `Agents.md`, `agents.md`, or configurable fallback names. This adds cross-platform ambiguity on case-insensitive filesystems and makes the first production contract less clear.

### Discover project files from git root to cwd

Deepy should find the nearest ancestor containing `.git` and use it as the project root. If no git root exists, Deepy should treat the current working directory passed into prompt construction as the only project directory. From that root, it walks to cwd and loads at most one `AGENTS.md` per directory.

This matches the user's expectation that subdirectories can override broader project guidance without inventing a separate rule metadata format.

### Merge order and precedence

The merged prompt should be:

1. `~/.deepy/AGENTS.md`
2. project root `AGENTS.md`
3. intermediate directory `AGENTS.md` files
4. cwd `AGENTS.md`

This keeps broader instructions earlier and more specific instructions later. The system prompt must explicitly say that direct user instructions override all loaded `AGENTS.md` content, and deeper `AGENTS.md` files override parent/global instructions when conflicts exist.

### Bound the instruction budget with leaf-first preservation

The loader should enforce a default maximum byte budget for the merged instruction block, using a constant such as `AGENTS_MD_MAX_BYTES = 32 * 1024`. Budget accounting should include source annotations and separators.

If content must be truncated, allocate budget from the end of the discovery list backward. This preserves cwd and nearby subdirectory guidance before parent and global guidance because the most specific rules are most likely to matter for the active task.

### Keep source annotations inside the merged block

Each loaded block should be wrapped with a source marker such as:

```md
<!-- From: /path/to/AGENTS.md -->
...
```

Source annotations make prompt debugging and model reasoning easier without requiring a separate metadata channel.

### Strengthen prompt contract, not create a hard policy engine

`AGENTS.md` contents are still prompt context, not an executable policy system. The prompt should say they are binding project/user guidance unless they conflict with higher-priority instructions, safety constraints, or the user's latest explicit request.

Deepy should also instruct the model to check for more specific `AGENTS.md` files before editing files outside the initially loaded cwd path, because future workflows may touch sibling directories that were not included in startup discovery.

### Add `/init` as a model-driven repository analysis command

The `/init` slash command should send a purpose-built prompt to the current Deepy agent. The prompt asks the agent to inspect the repository, read any existing project root `AGENTS.md`, and create or update only that file. This follows Kimi's model-driven approach while using a tighter prompt inspired by the Deepcode/OpenCode-style contributor-guide template: concise headings, repository-specific commands, architecture, style, verification, and boundaries.

The command should run through the normal Deepy model/tool path rather than a local static generator. A static generator would be faster, but it cannot accurately infer project-specific commands and conventions. Running through the normal agent path also reuses existing tool permissions, transcript rendering, usage reporting, and session persistence.

### Show an AGENTS.md-loaded status indicator

The interactive footer should show `AGENTS.md loaded` when the current working directory has applicable global or project `AGENTS.md` instructions. This is intentionally a presence indicator, not a file count or precedence display, so the footer stays compact.

## Risks / Trade-offs

- Conflicting markdown rules can still confuse the model -> Mitigate with explicit precedence text and source ordering.
- Large global files may be truncated -> Mitigate by leaf-first budget allocation and documentation that global rules should be concise.
- Loading only the cwd path may miss sibling subtree `AGENTS.md` files -> Mitigate with prompt guidance to inspect nearby `AGENTS.md` before editing files in subdirectories outside the loaded chain.
- Dropping fallback names may surprise early testers -> Mitigate with documentation and because the old feature has no formal compatibility burden.
- `AGENTS.md` is prompt guidance, not guaranteed enforcement -> Mitigate by making rules concrete, source-scoped, and covered by tests for discovery and injection behavior.
- `/init` quality depends on the model's project analysis -> Mitigate with a focused prompt, source-grounding requirements, and normal user review of the generated `AGENTS.md`.
- Footer checks should stay cheap -> Mitigate with a lightweight existence/non-empty check instead of rendering the full instruction block for display.

## Migration Plan

1. Replace the current fixed candidate list with a hierarchical `AGENTS.md` discovery function.
2. Keep `~/.deepy/AGENTS.md` as the global Deepy file and remove any plan to use `~/.agents/AGENTS.md`.
3. Update system prompt wording around project instructions and precedence.
4. Add `/init` to slash command discovery, help text, and interactive handling.
5. Update README files with the new locations, recommended structure, and `/init` command.
6. Add tests for discovery order, precedence text, budget behavior, no-git fallback, empty file skipping, non-supported filenames, and `/init` routing.

Rollback is straightforward: revert the loader and prompt wording to the previous two-file behavior. No persistent data migration is required.
