# Deepy plan-2 实施计划

## Summary

按 `spec/plan-2.md` 继续完善 Deepy Python 版，方向改为“纯 Python Agent 项目”，不再追求与 JS 版完全一致。实施重点是：真实 DeepSeek 最小冒烟验证、API key 首次引导、OpenAI Agents SDK 更深接入、准确 usage 统计、Rust-backed 性能库、prompt_toolkit/Rich 交互体验，以及移除旧 deepcode-cli 兼容负担。

## Status Legend

- `[x]` 已完成并有测试或命令验证。
- `[~]` 已有实现但仍需补充验证或体验打磨。
- `[ ]` 未完成或需后续实现。

## Tasks

### A. Config / API Key

- [x] `P2-01` TOML-only 配置 - 已完成并有测试或命令验证 - 验收：拒绝 `.json` 配置；默认配置写入 `~/.deepy/config.toml`；保留 1M context 和 80% compact 默认值。
- [x] `P2-02` `deepy config init` - 已完成并有测试或命令验证 - 验收：支持 `--api-key`、`--model`、`--base-url`、`--force`；写入权限为 `0600`；不写 JSON。
- [x] `P2-03` `deepy config setup` - 已完成并有测试或命令验证 - 验收：打印 DeepSeek API key 页面；使用 `prompt_toolkit` 密码输入；可配置 key、model、base_url；写入 TOML 且权限 `0600`。
- [x] `P2-04` 交互模式缺 key 引导 - 已完成并有测试或命令验证 - 验收：启动交互模式时无 API key 会先进入 setup；不自动打开浏览器。
- [x] `P2-05` `deepy doctor --json` 缺 key 稳定失败 - 已完成并有测试或命令验证 - 验收：无 key 时返回非 0；提示 `deepy config setup`；不输出明文 key。

### B. OpenAI Agents SDK / DeepSeek Provider

- [x] `P2-06` DeepSeek 使用 `OpenAIChatCompletionsModel` - 已完成并有测试或命令验证 - 验收：provider 通过 `AsyncOpenAI(base_url, api_key)` 构建；禁用 tracing sensitive data。
- [x] `P2-07` 统一 provider/model settings - 已完成并有测试或命令验证 - 验收：普通 run、interactive run、live doctor 复用同一 provider/model settings 构造逻辑。
- [x] `P2-08` DeepSeek thinking 配置 - 已完成并有测试或命令验证 - 验收：默认 thinking enabled；reasoning effort 默认 `max`；`ModelSettings(include_usage=True, store=False)`。
- [x] `P2-09` AskUserQuestion 保持 SDK tool flow - 已完成并有测试或命令验证 - 验收：pending question 状态继续可用；不强行迁移到 SDK HITL。

### C. Live Doctor

- [x] `P2-10` 新增 `deepy doctor --live` - 已完成并有测试或命令验证 - 验收：发送固定短 prompt `Reply with OK.`；max turns 为 1；无工具；不写 session。
- [x] `P2-11` live 输出结构 - 已完成并有测试或命令验证 - 验收：输出 model、base_url、ok、response_summary、usage；API key 只显示 configured/masked。
- [x] `P2-12` live smoke 验证 - 已完成并有测试或命令验证 - 验收：`DEEPY_LIVE_API=1 uv run deepy doctor --live --json` 成功返回 OK 和 usage；不作为默认 CI。

### D. Usage

- [x] `P2-13` 新增 `TokenUsage` - 已完成并有测试或命令验证 - 验收：支持 prompt、completion、total、cache hit、cache miss、reasoning、request entries。
- [x] `P2-14` DeepSeek usage 归一化 - 已完成并有测试或命令验证 - 验收：兼容 `prompt_tokens`、`completion_tokens`、`total_tokens`、`prompt_cache_hit_tokens`、`prompt_cache_miss_tokens`、`completion_tokens_details.reasoning_tokens`。
- [x] `P2-15` Agents SDK usage 归一化 - 已完成并有测试或命令验证 - 验收：兼容 SDK `input_tokens`、`output_tokens`、`input_tokens_details`、`output_tokens_details`。
- [x] `P2-16` `RunSummary.usage` - 已完成并有测试或命令验证 - 验收：stream event 或 run result 的 usage 会进入 `RunSummary`。
- [x] `P2-17` session usage 累计 - 已完成并有测试或命令验证 - 验收：每轮 run 后累计写入 session index；缺失 usage 时显示 `usage=unknown`。
- [x] `P2-18` usage 展示 - 已完成并有测试或命令验证 - 验收：`sessions list`、`sessions show`、exit summary、interactive usage footer 可显示 usage 和 reasoning tokens。

### E. Session / Schema

- [x] `P2-19` 清理 JS legacy replay - 已完成并有测试或命令验证 - 验收：不再读取 `entries`、`createTime`、`updateTime`、`contentParams`、`messageParams` 作为兼容回放来源。
- [x] `P2-20` Deepy Python JSONL 新格式 - 已完成并有测试或命令验证 - 验收：新记录包含 `session_id`、`role`、`content`、`created_at`、`meta.sdk_item`；回放只读取 `meta.sdk_item`。
- [x] `P2-21` fixtures 改为新格式 - 已完成并有测试或命令验证 - 验收：session fixture 不再依赖旧 JS schema；测试覆盖新增、追加、resume、pop、clear、usage 累计。
- [x] `P2-22` 用户命令保留 - 已完成并有测试或命令验证 - 验收：`/resume`、`sessions list`、`sessions show` 仍可用，但不承诺读取 JS 历史。

### F. Performance / Rust-backed Libraries

- [x] `P2-23` 引入 `orjson` - 已完成并有测试或命令验证 - 验收：JSON、JSONL、debug log、error log 编解码走 `orjson` 快速路径，并有 stdlib fallback。
- [x] `P2-24` 引入 `tiktoken` - 已完成并有测试或命令验证 - 验收：本地 token 估算优先使用 `cl100k_base`，失败时回退长度估算。
- [x] `P2-25` 保持 pydantic-core 依赖路径 - 已完成并有测试或命令验证 - 验收：继续使用 `pydantic>=2`，不新增自研 Rust extension。

### G. UI / Interaction

- [x] `P2-26` Enter 发送，Shift+Enter 换行 - 已完成并有测试或命令验证 - 验收：普通 Enter 提交 prompt；常见 xterm/Kitty Shift+Enter 序列插入换行；测试覆盖按键映射。
- [x] `P2-27` prompt_toolkit 基础能力 - 已完成并有测试或命令验证 - 验收：history、slash completion、Esc interrupt、多行输入可用。
- [x] `P2-28` Rich UI 体验打磨 - 已完成并有测试或命令验证 - 验收：欢迎屏、tool call/tool result、usage footer 使用统一语义色；失败工具输出和错误提示使用明确错误色；测试覆盖 terminal/message/welcome 相关展示。
- [x] `P2-29` loading/status line usage - 已完成并有测试或命令验证 - 验收：loading/status helper 可附加已知 usage；stream usage event 会在终端输出；测试覆盖 loading usage suffix 和 terminal usage event。
- [x] `P2-30` 错误分类展示 - 已完成并有测试或命令验证 - 验收：config 缺失路径明确；API auth、网络、SDK/tool failure 有用户可见分类和 hint；CLI run/live doctor 使用分类后的错误展示。

### H. Verification

- [x] `P2-31` 单元测试 - 已完成并有测试或命令验证 - 验收：覆盖 config setup、usage normalization、session 新格式、prompt input、exit summary、fixtures。
- [x] `P2-32` 集成检查 - 已完成并有测试或命令验证 - 验收：`uv run pytest`、`uv run ruff check`、`uv run pyright` 通过。
- [x] `P2-33` build 检查 - 已完成并有测试或命令验证 - 验收：`uv build` 成功生成 sdist/wheel。
- [x] `P2-34` doctor 无 key 场景 - 已完成并有测试或命令验证 - 验收：`deepy --config <empty-config> doctor --json` 非 0，提示 setup。
- [x] `P2-35` live smoke - 已完成并有测试或命令验证 - 验收：`DEEPY_LIVE_API=1 uv run deepy doctor --live --json` 成功返回 OK 和 usage，且无明文 key。

## Assumptions

- 真实 API 验证采用“最小冒烟”。
- 兼容清理采用“纯新版”，不继续保留 JS 历史格式读取能力。
- API key 不写入代码、不写入测试 fixture、不出现在日志明文中。
- Rust 优化优先采用成熟 Python 包里的 Rust-backed 实现，例如 `orjson`、`pydantic-core`、`tiktoken`；暂不引入自研 Rust crate。
- JS 项目仅作为参考，不再作为完成标准或保留对象。
