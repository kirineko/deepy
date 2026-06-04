## Why

Deepy already has status surfaces, but `/status` is not consistently discoverable and does not answer the two questions users check most often during an interactive coding session: how much API usage this session/project has consumed, and whether the DeepSeek account still has usable balance. The existing stable exit panel also uses a separate visual treatment and only appears for `/exit`, while confirmed Ctrl+D exits without a panel; the experimental TUI also exits without a matching panel. Status and exit should share a compact, redesigned summary language without forcing users to leave the terminal.

## What Changes

- Promote `/status` to a first-class discoverable interactive command in the stable terminal UI.
- Extend status reporting with compact token usage for the active session and project-level session index when available.
- Query DeepSeek's `/user/balance` endpoint only when the user explicitly runs `/status`, then display account availability plus per-currency balance totals.
- Keep balance lookup failure non-fatal with concise unavailable/error text.
- Preserve existing Context Window semantics by keeping cumulative Token Usage separate from latest request context occupancy.
- Update the experimental Textual TUI `/status` screen to show the same local usage and balance information.
- Redesign the stable exit summary panel around the same compact usage/status visual language.
- Show the stable exit summary for `/exit`, `/quit`, and confirmed Ctrl+D exits.
- Show a matching exit summary panel when the experimental Textual TUI exits through `/exit` or confirmed Ctrl+D.
- Keep secrets masked; `/status` SHALL never print the configured API key.
- Keep exit summaries local-only; exit paths SHALL NOT call the DeepSeek balance endpoint.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `terminal-ui`: Make `/status` discoverable, render a compact status panel with usage, context, runtime, and balance fields, and redesign the stable exit summary panel.
- `session-context`: Define status-panel usage scopes and reinforce that cumulative Token Usage is separate from Context Window occupancy.
- `deepseek-provider`: Add an on-demand DeepSeek account balance lookup contract using the configured API key and official balance endpoint.
- `experimental-textual-tui`: Update the Textual `/status` auxiliary view to surface the same usage and balance summary, and show the redesigned exit summary when the TUI exits.

## Impact

- Affected code: `src/deepy/status.py`, `src/deepy/ui/exit_summary.py`, `src/deepy/ui/slash_commands.py`, `src/deepy/ui/terminal.py`, `src/deepy/tui/app.py`, and focused tests around status, usage, slash commands, exit summary panels, and TUI status/exit screens.
- Affected APIs: read-only HTTP `GET /user/balance` against DeepSeek's configured API host when `/status` is invoked; no startup, footer, doctor, idle status, or model-turn path should call it.
- Affected data: reads existing session index usage records; no session format migration is expected.
- Dependencies: prefer existing HTTP/OpenAI client stack if suitable; otherwise add only a small standard-library or existing-dependency HTTP helper.
