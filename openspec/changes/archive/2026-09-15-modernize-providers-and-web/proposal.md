## Why

当前 provider 与模型目录、API 路径和图片能力判断已经落后于实际接口，单一 `[model]` 配置还会在切换 provider 时覆盖其他服务的密钥。本次根据已完成的接口调研，统一模型调用、替换内置联网后端，并让多 provider 配置与图片输入可靠共存。

## What Changes

- **BREAKING**：provider 固定为 `deepseek`、`mimo`、`kimi`、`cli_proxy`，删除 OpenRouter，移除旧 `xiaomi` / `localhost` 标识及旧模型目录，不提供兼容别名。
- 模型目录：DeepSeek V4.1 Flash（`deepseek-flash`，全局默认）；MiMo 2.5 / 2.5 Pro（`mimo-v2.5` / `mimo-v2.5-pro`）；Kimi K3（`kimi-k3`）；CLI Proxy 的 `gpt-6-astra`、`gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna`、`gpt-5.5`。
- **BREAKING**：主 agent、subagent、输入建议、摘要与压缩等模型调用全部走 Responses API，按 provider 适配推理参数、工具调用、流式事件、历史重放及 usage；移除 Chat Completions 专属实现。
- 内置 `WebSearch` 统一通过独立 DeepSeek `deepseek-flash` + Anthropic Messages `web_search_20250305` 实现，所有对话 provider 均可调用。该路径是唯一的模型 API 例外，不挂载各对话 provider 的原生搜索。
- **BREAKING**：删除 SearXNG、`s.kirineko.tech`、DuckDuckGo 回退和旧搜索查询预处理。保留本地 HTTP `WebFetch`；不宣称 DeepSeek 原生 web fetch 可用。Tavily 等 MCP 配置、搜索优先策略与 subagent 继承规则保持有效。
- **BREAKING**：TOML 改为独立 provider profiles 和 `active_provider`。每个 profile 独立记忆 key、URL、model、reasoning；切换和局部设置只更新目标字段。环境变量按 provider 解析，不将解析后的环境密钥写回配置；不自动迁移旧共享 `[model]` 格式。
- 建立按 provider/model/API 判定的能力目录。启用 DeepSeek Flash、MiMo 2.5、Kimi K3 及上述五个 CLI Proxy 模型的 Responses 图片输入；MiMo 2.5 Pro 不支持图片。同步 classic/modern UI、附件校验、图片工具结果、会话重放和压缩；本次不新增音频、视频、PDF 原生输入或媒体生成。
- 搜索结果必须来自真实结构化搜索记录，提供可用来源与可恢复错误；搜索 usage 单独归属 DeepSeek，不污染当前对话的上下文占用。同步中英文用户文档与回归测试。

## Capabilities

### New Capabilities

无；扩展现有行为合约。

### Modified Capabilities

- `configuration`: provider profiles、独立环境密钥、模型目录、推理配置、局部持久化与能力元数据。
- `deepseek-provider`: 全 provider Responses 构建、推理映射、工具与历史重放、辅助调用及图片序列化；移除过时兼容路径。
- `tools`: DeepSeek Messages 内置搜索、结构化结果与失败边界、保留 MCP 搜索优先和本地 WebFetch。
- `image-understanding-input`: 新模型图片矩阵、Responses 内容块、模型切换与附件限制。
- `input-suggestions`: provider 内固定建议模型与 Responses 调用、实际模型 usage 标识。
- `session-context`: 独立搜索 usage 与跨模型图片历史处理。
- `subagents`: 明确模型覆盖的 provider 解析与统一 Responses 调用。
- `terminal-ui`: 新 provider/model 选择、profile 恢复与独立凭据编辑。
- `experimental-textual-tui`: modern UI 同步 provider 选择与 profile 保存行为。
- `user-documentation`: 双语配置、API、联网与多模态能力说明。

## Impact

涉及 `src/deepy/config`、`src/deepy/llm`、`src/deepy/input_suggestions.py`、`src/deepy/tools/web`、工具注册/提示词、session usage 与附件处理、两套 UI 的配置/模型选择，以及 CLI doctor、测试、README 和 docs。保留 OpenAI Agents SDK 与现有工具、会话、MCP 架构；仅为搜索增加独立 Messages HTTP adapter。

升级需要重新建立 provider profiles，旧配置在用户主动重新配置前保持原文件并给出明确说明。搜索需要独立可用的 DeepSeek key，即使当前对话使用 MiMo、Kimi 或 CLI Proxy；未配置时仅搜索不可用。先前直连 smoke test 证明了接口入口可行，不替代实施阶段 SDK 多轮、流式、UI 与回归验证。本 proposal 不包含实现、版本发布或 Git 推送。
