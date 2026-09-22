# Changelog

[简体中文](CHANGELOG.zh-CN.md)

## 0.2.34 — 2026-09-22

- Replace MiMo V2.5 / V2.5 Pro with `mimo-v2.6-flash` / `mimo-v2.6-pro`.
- Support image input on both models through Responses, including pasted images, Read results, session history and subagents. Deepy's native input remains text and images; audio/video input and media generation are not enabled.
- Use V2.6 Flash by default and for input suggestions with thinking disabled. Both models retain `enabled` / `disabled` thinking and MiMo tool-schema compatibility.
- Use a conservative 1,000,000-token context window and documented 131,072-token output ceiling; the default request output budget remains 32,768 tokens.
- Add specific, non-mutating recovery guidance for retired model selections and model-limit overrides, including inactive provider profiles.

### Upgrade from MiMo V2.5

This release removes both old model IDs from Deepy's catalog. Xiaomi schedules their service retirement for **2026-10-21 10:00 (Asia/Shanghai)**. See the [official model list](https://mimo.mi.com/docs/zh-CN/quick-start/summary/model).

In your existing TOML configuration, update `model` under `[providers.mimo]`:

| Old model | Replacement |
| --- | --- |
| `mimo-v2.5` | `mimo-v2.6-flash` |
| `mimo-v2.5-pro` | `mimo-v2.6-pro` |

Rename the model ID in any corresponding `[providers.mimo.model_limits."<model-id>"]` table, or remove that override. Keep credentials, URL, reasoning and valid limit values. Inactive MiMo profiles also need updating. Deepy does not silently migrate files or rewrite historical session model identities.
