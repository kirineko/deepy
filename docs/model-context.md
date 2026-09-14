# Model context and switching

Deepy resolves context and output budgets for the selected provider/model. Omitting
`context.window_tokens` follows the model; an explicit value is a global safety
cap. A cap never enlarges a model's documented or conservative runtime limit.
`deepy config show --json` and `deepy doctor` show resolved limits and their sources.
Loading or displaying settings never writes inferred limits to your config.

## Limits checked on 2026-09-15

| Provider/model | Documented window | Runtime window | Output ceiling used | Evidence |
| --- | --- | --- | --- | --- |
| DeepSeek / deepseek-flash | 1M | 1,000,000 | 384,000 (conservative 384K) | [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/) |
| MiMo / mimo-v2.5 | 1M | 1,000,000 | 128,000 (conservative 128K) | [MiMo](https://mimo.mi.com/docs/zh-CN/quick-start/summary/model) |
| MiMo / mimo-v2.5-pro | 1M | 1,000,000 | 128,000 (conservative 128K) | [MiMo](https://mimo.mi.com/docs/zh-CN/quick-start/summary/model) |
| Kimi / kimi-k3 | 1M | 1,000,000 | 1,048,576 parameter ceiling | [Models](https://platform.kimi.com/docs/models), [Responses](https://platform.kimi.com/docs/api/responses) |
| CLI Proxy / gpt-6-astra | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-6-astra) |
| CLI Proxy / gpt-5.6-sol | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.6-sol) |
| CLI Proxy / gpt-5.6-terra | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.6-terra) |
| CLI Proxy / gpt-5.6-luna | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.6-luna) |
| CLI Proxy / gpt-5.5 | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.5) |

Nominal 1M does not establish binary units. Those windows are labeled
`conservative`; exact official counts remain unknown. CLI Proxy uses OpenAI
reference limits with `proxy-unverified`: `/models` does not report deployment
limits, and short requests do not verify maximum context. Kimi's output parameter
ceiling is separate from input length and is not proof of a larger context.
Where the shared input/output relationship is unconfirmed, Deepy conservatively
budgets input and output together; these are request policies, not new provider claims.

## Smaller caps and output budgets

Quote model IDs containing dots in TOML:

```toml
[context]
# Optional global cap; omit to follow the selected model.
# window_tokens = 900000
compact_trigger_ratio = 0.8
reserved_context_tokens = 50000

[providers.cli_proxy.model_limits."gpt-5.6-terra"]
context_window_tokens = 128000
max_output_tokens = 16384
```

The effective window is the minimum of catalog, explicit global cap and model
cap. `max_output_tokens` is a per-request output budget; it is not the model's
physical maximum. Main and subagent requests default to 32,768; summaries use at
most 8,192; suggestions retain 2,048 and their existing model/thinking settings.
Invalid values, unknown models, excessive caps and windows unable to fit the
output plus reserve are rejected before saving. Other provider profiles and keys
remain unchanged. Removing a cap restores the model default.

Let I be estimated complete input, W the effective window, O requested output,
and R = max(reserved_context_tokens, O + 4096). Deepy prepares compaction when
I >= ceil(W × compact_trigger_ratio) or I + R >= W, and requires I + R < W
before sending. Output is reserved once. System prompts, actual tool/MCP schemas,
history, new input, tool results and normalized image parts count toward I;
base64 is not treated as prose. Counts use an approximate tokenizer and image
allowance. Matching usage checkpoints calibrate history without hiding new input.
Search and suggestion usage remain separate from conversation occupancy; summary
usage is recorded even when a later migration step fails.

## History and recovery

`/model` keeps the session and original messages. Switching is rejected during
active generation, tools, approval or subagent work. Selection is saved while idle;
preparation happens before sending, not while browsing the picker. The single
`ctx` area shows target limits and an estimate until matching usage is available.
Reasoning from another provider, model or endpoint is excluded from the replay
view, while original records and complete tool-call/result groups remain intact.
Resume and switching back always revalidate against the current budget and prefix.

For a text-only target with image history, switch back, start a new text session,
or explicitly run `/compact --for-model`. That command permits a potentially
lossy image-to-text summary using the session's last successful, still-configured
image-capable source model. Deepy announces that model before calling it; it never
selects an unrelated account. Originals are retained in the session's existing
SQLite archives. Ordinary `/compact [focus]` remains available.

Summaries are split only at complete history/tool boundaries. Each summary and
merge must fit its own model budget. Preparation is limited to 32 requests and
60 seconds per request and can be cancelled. Failure, cancellation, stale history
or an indivisible oversized tool group stops preparation without replacing the
active view. Draft and attachments remain available. Only a fully checked result
is committed transactionally. A tool continuation that cannot fit stops before
the next HTTP request and retains executed results; it does not rerun tool effects.

The opt-in `scripts/smoke_model_history.py` uses temporary sessions, standard key
environment variables and small text/tool/image requests. It does not measure
maximum context, change your saved config or certify proxy deployment limits.

Footer example: `ctx 12.5K/1M~ (1.3%)`. A leading `~` marks estimated usage; a trailing `~` on the window marks a conservative limit, and `?` an unverified proxy limit. `-` means unknown usage; a final `!` means compaction is due. Remaining tokens and long state labels are omitted from the footer; `/status` and `deepy doctor` retain full numbers, sources and readiness details.

Summary batches also enforce the 32 MiB encoded request-body limit, including images, summary instructions, focus/todo context and tool definitions. Planning leaves serialization headroom; independent image groups are split before sending. An indivisible oversized tool group is rejected with the original history intact.
