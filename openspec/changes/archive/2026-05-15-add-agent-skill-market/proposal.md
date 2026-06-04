## Why

Deepy needs a standards-compatible skill system and a simple distribution path for users who cannot reliably fetch and unpack skills from GitHub. The existing `.deepy/skills` path is private to Deepy and has not been validated in real use, so this is the right point to replace it with the Agent Skills directory convention.

## What Changes

- **BREAKING**: Remove support for project skills under `.deepy/skills`.
- Discover standard Agent Skills from `~/.agents/skills` and `<project>/.agents/skills`.
- Add built-in `skill-creator` and `skill-installer` skills shipped with Deepy and loaded specially without copying them into `.agents/skills`.
- Replace harness-side keyword skill matching with progressive disclosure: Deepy injects skill metadata and exposes a `load_skill` tool for loading complete `SKILL.md` content on demand.
- Add `/skills` management commands and `/skill:<skill-name>` active invocation, with slash completion after `/skill:`.
- Add a lightweight skill market client that browses, installs, uninstalls, and lists skills from `https://skill.kirineko.tech`.
- Add a separate `services/skill-market` subproject for the upload/query/download service. It is included in this repository for development but can be deployed and later moved out independently.

## Capabilities

### New Capabilities
- `agent-skills`: Discovery, prompting, invocation, and management of Agent Skills in Deepy.
- `skill-market`: Online skill browsing, upload ingestion, download, and local installation management.

### Modified Capabilities
- `terminal-ui`: Slash command behavior changes to support `/skills` subcommands and `/skill:<skill-name>` completion/invocation.

## Impact

- Affects `src/deepy/skills.py`, prompt assembly, runner behavior, tool registration, slash command parsing/completion, terminal UI handlers, status reporting, and docs.
- Adds bundled skill data under Deepy's package data.
- Adds a market client and local installation metadata under `~/.deepy`.
- Adds a development-only market service subproject under `services/skill-market`.
- Updates tests that currently assume `.deepy/skills` and keyword-based auto-loading.
