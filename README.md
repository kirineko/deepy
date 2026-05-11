Deepy is a Python terminal coding agent for DeepSeek OpenAI-compatible models.

The command name is:

```bash
deepy
```

Current migration status:

- TOML config lives at `~/.deepy/config.toml`.
- DeepSeek V4 models default to thinking mode.
- The model adapter uses the OpenAI Agents SDK `OpenAIChatCompletionsModel`.
- Session history is stored as project-scoped JSONL files for inspectability.
- Context input uses a 1M token window and compacts above the configured threshold.
- Project rules from `AGENTS.md` and skills from `.deepy/skills/*/SKILL.md` are injected into the system prompt.
- A minimal Rich terminal shell is available while the full TUI is being migrated.

Useful commands:

```bash
deepy --version
deepy config init --api-key sk-...
deepy config show
deepy doctor
deepy skills list
deepy skills show <skill-name>
deepy sessions list
deepy run --skill <skill-name> "say hello"
deepy run --session <session-id> "continue"
```

Interactive slash commands:

```text
/help
/skills
/skill <skill-name>
/use <skill-name>
/sessions
/resume <session-id>
/new
/exit
```
