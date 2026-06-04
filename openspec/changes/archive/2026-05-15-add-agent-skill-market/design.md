## Context

Deepy currently discovers user skills from `~/.agents/skills` and project skills from `.deepy/skills`, injects the discovered metadata into the system prompt, and resolves loaded skills before each run. Automatic loading is currently implemented in Deepy's harness by keyword scoring, which gives the application too much responsibility for deciding task relevance.

The target model is the Agent Skills progressive disclosure pattern used by Mini-Agent, Cline, Kimi, and Codex: always expose concise metadata, load complete instructions only when the model or user explicitly invokes a skill, and keep the skill directory format portable.

## Goals / Non-Goals

**Goals:**
- Make Deepy fully use the Agent Skills directory convention: `~/.agents/skills` and `<project>/.agents/skills`.
- Provide built-in `skill-creator` and `skill-installer` skills without requiring installation into `.agents/skills`.
- Support user-driven invocation through `/skill:<skill-name>` and management through `/skills` subcommands.
- Support completion and discoverability when the user types `/skill:`.
- Replace keyword auto-loading with a `load_skill` tool and system-prompt guidance.
- Provide a minimal market service and client for admin-uploaded skill zip files.
- Keep market metadata constrained to data available from the uploaded package and server upload event.

**Non-Goals:**
- No general plugin runtime, hooks, MCP server registry, or arbitrary executable tool marketplace.
- No GitHub-based install/update flow in the first implementation.
- No migration layer for `.deepy/skills`.
- No user accounts, ratings, payments, or recommendation system in the market.

## Decisions

1. **Use only Agent Skills paths for user/project skills.**

   Deepy will discover project skills at `<project>/.agents/skills` and user skills at `~/.agents/skills`. Project wins over user, and both win over built-in skills. The old `.deepy/skills` path is removed because it has not been formally used and would preserve a Deepy-specific fork of the standard.

2. **Add built-in skills as a third discovery scope.**

   Built-in skills live in Deepy's package data and are rendered as `Built-in skills` in the available-skills prompt block. They are not installed or copied into user directories. This keeps `skill-creator` and `skill-installer` always available while preserving the portability of user-installed skills.

3. **Use progressive disclosure instead of harness keyword loading.**

   The system prompt will instruct the model that available skills are metadata only and that it MUST call `load_skill` before relying on a skill's detailed instructions. The `load_skill` tool returns the complete `SKILL.md` body plus the skill root path so scripts/references/assets can be resolved. Explicit `/skill:<name>` invocation bypasses relevance detection and starts a turn with that skill loaded.

4. **Use `/skills` for management and `/skill:<name>` for active invocation.**

   `/skills` opens/list-renders the management surface. `/skills list`, `/skills search`, `/skills install`, `/skills uninstall`, `/skills show`, `/skills use`, `/skills installed`, and `/skills update` are first-class subcommands. `/skill:<skill-name> [request]` actively invokes a skill. Slash completion must include installed skill names after the `/skill:` prefix so users can discover the syntax.

5. **Keep the market service upload-centered.**

   The server accepts an admin-uploaded zip, validates/extracts it, parses `SKILL.md`, stores the original zip and extracted snapshot, and writes database rows from verified package content and upload metadata. Since packages are expected to be mostly immutable, version support is simple: a skill can have multiple uploaded versions, but clients install the latest active version by default.

6. **Make local install metadata separate from skill content.**

   Installed market skills are copied into `.agents/skills/<name>` and accompanied by Deepy-local metadata under `~/.deepy/skill-market/installed.json`. This allows uninstall/update checks without adding market-specific files to the skill directory.

## Risks / Trade-offs

- **Skill names conflict with built-in commands** -> Use `/skill:<name>` instead of `/<name>` and detect duplicate skill names during discovery.
- **The model forgets to load a relevant skill** -> Strong system-prompt guidance plus an explicit `load_skill` tool; explicit slash invocation remains available.
- **Uploaded zip has unexpected layout** -> Validate exactly one root skill or one discoverable `SKILL.md`; reject ambiguous multi-skill packages in the first market implementation.
- **Users modify installed skills locally** -> Track installed hash and warn before uninstall/update if local content differs.
- **Market service becomes coupled to Deepy release** -> Keep it in `services/skill-market` with its own pyproject and no runtime import dependency from Deepy.

## Migration Plan

1. Replace `.deepy/skills` discovery/tests/docs with `.agents/skills`.
2. Add built-in skill package data and discovery scope.
3. Add `load_skill` tool and remove prompt keyword matching.
4. Replace legacy `/skill NAME` and `/use NAME` skill commands with `/skills` subcommands and `/skill:<name>` active invocation.
5. Add market client and local install metadata.
6. Add `services/skill-market` as a standalone FastAPI subproject.
7. Update README and Chinese README with new paths and commands.
