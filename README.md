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

Useful commands:

```bash
deepy --version
deepy config show
deepy doctor
```
