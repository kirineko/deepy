# DeepSeek Cache Diagnostics

Deepy tracks DeepSeek cache-prefix metadata per session. Normal usage does not
log provider payloads, authorization headers, or API keys.

## Optional live probe

The optional cache probe is for local diagnostics only:

```bash
DEEPSEEK_API_KEY=... DEEPSEEK_PROBE_MODEL=deepseek-v4-pro uv run python scripts/probe_deepseek_cache.py
```

To probe the same OpenAI Agents SDK path used by Deepy's runtime model wrapper:

```bash
DEEPSEEK_API_KEY=... DEEPSEEK_PROBE_MODEL=deepseek-v4-pro uv run python scripts/probe_agents_sdk_cache.py
```

The scripts send DeepSeek request sequences with the selected probe model and
print only cache hit, cache miss, and hit-ratio numbers for warm, append-only,
and mutated-prefix requests. Do not commit API keys, shell history exports, or
captured provider payloads.

The normal test suite does not require network access or a DeepSeek API key.
