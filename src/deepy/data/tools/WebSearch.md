## WebSearch

Use `WebSearch` when current or external information is required and the configured search backend is available.

Parameters:

- `query`: The search query.

Behavior:

- A configured local command is preferred.
- A configured API endpoint may be used when present.
- If no backend is configured, the tool returns a clear failure result.
