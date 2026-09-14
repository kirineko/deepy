## WebSearch

Search current information using DeepSeek Flash's native search through an independent Messages API request.

Use a concise query. Results contain source titles, URLs and available snippets. An empty result means a real search returned no sources; errors and partial results are explicitly identified. Do not present missing search records as successful browsing.

Requires the DeepSeek profile key or DEEPSEEK_API_KEY independently of the active conversation provider. Prefer configured search-class MCP tools when instructed; this tool remains the built-in fallback. Use WebFetch to read a specific URL.

Each request is bounded to three server searches, 4096 output tokens, sixty seconds and ten displayed sources. Search consumes separate DeepSeek usage. Do not repeatedly retry a failed search without a reason.
