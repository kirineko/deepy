## 1. Skill Discovery And Built-ins

- [x] 1.1 Replace `.deepy/skills` discovery with project `.agents/skills` and user `~/.agents/skills`.
- [x] 1.2 Add built-in `skill-creator` and `skill-installer` package data and include them as the lowest-priority discovery scope.
- [x] 1.3 Update skill formatting to show project, user, and built-in scopes deterministically.
- [x] 1.4 Update docs and tests that still reference `.deepy/skills`.

## 2. Progressive Disclosure Runtime

- [x] 2.1 Add a `load_skill` function tool that resolves a skill by name and returns its complete instructions and root path.
- [x] 2.2 Update system prompt guidance so the model uses `load_skill` when a task matches available skill metadata.
- [x] 2.3 Remove harness-side keyword skill matching from the runner.
- [x] 2.4 Preserve explicit skill loading for CLI/headless runs through `--skill`.

## 3. Slash Commands And Completion

- [x] 3.1 Replace legacy `/skill NAME` and `/use NAME` behavior with `/skills` subcommands.
- [x] 3.2 Implement `/skill:<name> [request]` active invocation.
- [x] 3.3 Add slash completion for `/skill:` with skill names and descriptions.
- [x] 3.4 Update terminal UI tests for `/skills` management and `/skill:<name>` invocation.

## 4. Market Client

- [x] 4.1 Add a market client for `skill.kirineko.tech` catalog and download endpoints.
- [x] 4.2 Implement `/skills search`, `/skills install`, `/skills uninstall`, `/skills installed`, and `/skills update` flows.
- [x] 4.3 Store market install metadata under `~/.deepy/skill-market/installed.json`.
- [x] 4.4 Protect uninstall/update when installed skill content has local modifications.

## 5. Skill Market Service

- [x] 5.1 Create standalone `services/skill-market` FastAPI subproject.
- [x] 5.2 Implement admin token protected zip upload with validation, extraction, hashing, and metadata parsing.
- [x] 5.3 Implement SQLite schema for skills and uploaded versions using only upload/package-derived metadata.
- [x] 5.4 Implement public catalog, detail, and latest active download endpoints.
- [x] 5.5 Add service tests for valid upload, invalid upload, search, and download.

## 6. Verification

- [x] 6.1 Run focused skill, slash command, market client, and service tests.
- [x] 6.2 Run the repository test suite or the broadest feasible subset.
- [x] 6.3 Run OpenSpec validation for `add-agent-skill-market`.
