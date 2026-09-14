## Context

动机与范围见 [proposal.md](proposal.md)。当前目录仍混合 DeepSeek/OpenRouter/Xiaomi Chat Completions 和 localhost Responses；输入建议另有 Chat Completions 路径。配置写入会重建单个 `[model]`，图片能力又分散在目录与硬编码白名单中。已有 OpenAI Agents SDK、FunctionTool、会话附件存储、classic/modern UI 和 MCP 搜索继承边界应继续复用。

以下是本次前序调研的点时结果（2026-09-14），不是生产 SLA，也不是已经完成 Deepy SDK 适配的声明：

| Provider / API model ID | Responses 文本 | Responses 图片 | 本次联网选择 |
|---|---|---|---|
| DeepSeek / `deepseek-flash` | 通过 | base64 测试图通过 | 独立 Messages 搜索通过；Flash Responses 搜索未产生真实搜索记录 |
| MiMo / `mimo-v2.5` | 通过 | base64 测试图通过 | 不使用 MiMo 原生搜索；Responses 网关拒绝该工具 |
| MiMo / `mimo-v2.5-pro` | 通过 | 404：无支持 image input 的 endpoint | 同上 |
| Kimi / `kimi-k3` | 通过 | base64 测试图通过 | 原生 Responses 搜索经请求调整后可用，本次不增加该分支 |
| CLI Proxy / `gpt-6-astra`、`gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna`、`gpt-5.5` | 五个均通过 | 五个均通过 | 原生搜索有真实记录，本次不挂载 |

图片测试使用简单四象限颜色图，只确认接口接收与基本识别；多图、工具结果、长历史和流式必须在实现阶段复测。CLI Proxy `/models` 还包含账户不能实际使用的 Spark 和非对话模型，不能把列表出现等同于可用。

DeepSeek Messages 的普通文本、流式、普通 function 两轮、图片 URL 和 `web_search_20250305` 已分别验证。搜索成功包含 `server_tool_use` / `web_search_tool_result`，并出现 `usage.server_tool_use.web_search_requests`。`web_fetch_20250910`、`web_fetch_20260209` 和测试过的 code execution 类型均被 400 拒绝；要求打开 URL 也不能证明实现了原生 fetch。新版 `web_search_20260209` 能调用，但测试中 `allowed_domains` 没有约束返回域名，因此不依赖该能力。

主要依据：

- [DeepSeek 当前模型定价目录](https://api-docs.deepseek.com/quick_start/pricing/)、[V4.1 Flash 发布说明](https://deepseek.com/news/deepseek-v4-1-flash/)、[Responses](https://api-docs.deepseek.com/guides/responses_api/)、[Anthropic 兼容 API](https://api-docs.deepseek.com/guides/anthropic_api/)。使用当前目录的 API ID；旧发布稿和搜索缓存不能覆盖最新接口说明及实际响应。
- [DeepSeek 官方 harness 搜索包](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/web/web-search-deepseek/README.md)、[provider 源码](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/web/web-search-deepseek/src/provider.ts)：独立 Messages 搜索和结构化解析的参考。
- [MiMo Responses](https://mimo.mi.com/docs/en-US/api/chat/responses)、[Codex 接入](https://mimo.mi.com/docs/en-US/tokenplan/integration/codex-configuration)：Responses 输入文本/图片；非 Pro 的其他模态宣传不能直接作为 Responses 能力。
- [Kimi Responses](https://platform.kimi.com/docs/api/responses)、[Kimi K3](https://platform.kimi.com/docs/guide/kimi-k3-quickstart)：图片使用 data URL；本次不适配 Chat Completions 视频输入。
- [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)：代理协议资料；实际模型能力仍由本地实例、账号与上游决定。

## Goals / Non-Goals

**Goals:**

- 使对话 transport、凭据解析、模型能力与 UI 选择共享同一事实来源。
- 保持 FunctionTool 和 session 边界，搜索独立于当前聊天 provider。
- 为每条修改后的行为提供可重复的回归验证，网络 smoke 与离线单测分开。

**Non-Goals:**

- 不引入通用 provider 插件框架、自动跨 provider 故障切换或 `/models` 全量自动上架。
- 不扩展到音频、视频、PDF 原生输入、ASR/TTS、图像生成、文件上传 API 或 provider 原生 web fetch。
- 不迁移旧配置，不保留 OpenRouter 和 Chat Completions 路径，不改变 MCP 接入、系统审计及 full reset 的授权语义。

## Decisions

### 1. 统一目录，保留 provider adapter

目录键是 `(provider_id, model_id, api)`，记录显示名、默认值、可用推理选项、图片能力和输入限制。API 不再作为用户可任意切换的配置项；所有目录模型固定 `responses`。目录驱动配置验证、两套 picker、CLI help、请求构建和图片能力判断。

| Provider | 默认 URL | 默认模型 | 用户推理选项 / 默认 |
|---|---|---|---|
| `deepseek` | `https://api.deepseek.com` | `deepseek-flash` | `none`, `high`, `max` / `max` |
| `mimo` | `https://api.xiaomimimo.com/v1` | `mimo-v2.5` | `disabled`, `enabled` / `enabled` |
| `kimi` | `https://api.moonshot.cn/v1` | `kimi-k3` | `low`, `high`, `max` / `max` |
| `cli_proxy` | `http://127.0.0.1:8317/v1` | `gpt-5.6-terra` | 按具体模型验证的 effort；默认 `medium` |

MiMo 的 Responses `none` 关闭推理，`low/medium/high` 均代表启用；UI 只暴露开关并将 enabled 映射为 `high`，避免虚假精细档位。DeepSeek 使用 Responses `reasoning.effort` 的 `none/high/max`，Kimi 使用 `low/high/max`，不发送旧 chat `thinking` / `reasoning_effort`。CLI 保留 `none/low/medium/high/xhigh` 的候选集合，但只为实际验证支持的模型暴露对应选项；不可假设全部模型支持所有 effort。Responses `reasoning.summary` 等可选字段同样由 adapter 控制，不能因使用 Responses 就套用 CLI 默认参数。

继续使用 OpenAI Agents SDK 的 Responses wrapper，通过小型 provider adapter 修正请求与响应差异。所有路径请求 usage 并关闭 provider-side storage；不依赖服务端持久化 `previous_response_id` 维持会话。多轮直接重放本地 Responses items，保留合法 call ID、function output 和 provider 要求的 reasoning 数据；不同 provider 的不透明 item 不直接相互转发。旧 Chat Completions reasoning alias/replay 全部删除。

不选择四套独立 runner：它们会重复工具、流式和会话逻辑。适配器聚焦协议边界；既有大模块新增行为时抽取 helper，避免继续膨胀。

### 2. Profiles 与运行时凭据分离

新配置示例（所有值均为非秘密示例）：

```toml
config_version = 2
active_provider = "deepseek"

[providers.deepseek]
model = "deepseek-flash"
base_url = "https://api.deepseek.com"
reasoning = "max"
api_key_env = "DEEPSEEK_API_KEY"

[providers.mimo]
model = "mimo-v2.5"
reasoning = "enabled"
api_key_env = "MIMO_API_KEY"

[providers.kimi]
model = "kimi-k3"
reasoning = "max"
api_key_env = "KIMI_API_KEY"

[providers.cli_proxy]
model = "gpt-5.6-terra"
reasoning = "medium"
api_key_env = "CLI_PROXY_API_KEY"
```

每个 profile 允许保存 `api_key` 或环境变量引用。解析优先级：该 profile 配置的非空 `api_key_env` 值 → 未自定义引用时的 provider 默认环境变量 → profile 保存的 `api_key` → 缺失。默认变量分别为 `DEEPSEEK_API_KEY`、`MIMO_API_KEY`、`KIMI_API_KEY`（缺失/空时允许 `MOONSHOT_API_KEY`）、`CLI_PROXY_API_KEY`。默认引用 `KIMI_API_KEY` 也允许该别名。移除通用 `DEEPY_API_KEY` 的跨 provider 覆盖；不持久化解析出的环境密钥。环境变量为空视为未提供。

写入采用读取原 TOML → 合并目标 profile/字段 → 私有临时文件 → 原子替换；保留 inactive profiles 及 context/MCP/UI 等其他配置。成功写入后才更新运行时选择；取消、未知配置路径和写入失败均保留原状态。provider 切换恢复其保存的完整 profile，仅首次使用才填默认值。已有 key 的密码输入留空表示保留；删除密钥必须是显式操作，不通过空白误删。

所有 profile 密钥都纳入 show/json、日志、异常与 diagnostics 的脱敏。会话保存 provider/model 身份与附件元数据，不保存 resolved key。新格式外的旧文件拒绝作为可运行配置并显示重新 setup 的指导；不猜测 URL 推断 provider，不自动覆写旧文件。用户完成明确的重新 setup 或 reset 才生成 v2；升级说明提醒先保留旧文件用于手动恢复。常规 setup 编辑 v2 profile 不等于 full reset。

### 3. 独立的 DeepSeek 搜索服务

请求固定到 `https://api.deepseek.com/anthropic/v1/messages`，不拼接当前聊天 base URL，也不使用 CLI/MiMo/Kimi key。读取 DeepSeek profile 的密钥解析结果，即使该 profile 未激活；使用 `x-api-key` 与 `anthropic-version: 2023-06-01`。不提供搜索 URL 自定义或第三方回退。

默认 `model=deepseek-flash`、`max_tokens=4096`，唯一内置工具为 `{"type":"web_search_20250305","name":"web_search","max_uses":3}`。每次 WebSearch 发送本次查询，不附带完整对话。设整体超时 60 秒、默认最多展示 10 个去重来源；若保留现有结果数量参数则限制为 1–10。不自动重试整个付费搜索请求；取消向 HTTP 请求传播。来源裁剪只控制下游上下文，不能宣称减少上游计费。

解析真实 `server_tool_use` 与对应 `web_search_tool_result`：校验 block 关联，区分有结果、真实搜索无结果、工具错误、缺少工具记录、部分结果后出错/截断。标准化 query、provider/model、标题、HTTP(S) URL、可用明文 snippet/citation、完成状态与 usage。只有不透明 encrypted content 时不伪造摘要、不把 opaque blob 交给 UI。模型 prose、HTTP 200、只有“我搜索了”的文字都不足以判定成功。部分结果必须标明不完整；无有效搜索记录返回可恢复结构化失败。

通过既有 WebSearch FunctionTool 暴露给主 agent 与允许该工具的 subagent；普通 Responses function call → 本地 Messages 请求 → function output。搜索不挂载到主模型的 Responses native tools，从而让 MiMo/Kimi/CLI 共用一致行为。保留 Tavily 等 MCP-first 指令、失败后内置工具可用性及 search-class MCP 继承规则。DeepSeek 是默认内置后端，不覆盖用户已有 MCP 优先策略。

缺少 DeepSeek key 时，非 DeepSeek 对话、MCP 和 WebFetch 继续工作，仅调用内置搜索时提示配置 `DEEPSEEK_API_KEY` 或 DeepSeek profile。WebFetch 继续本地 HTTP 抓取和可读内容抽取，不模拟 DeepSeek 原生 fetch。删除旧搜索 provider、query rewrite/translation、配置、依赖（确认无其他用途后）及提示词描述。

### 4. 图片能力与会话安全

八个已通过图片 smoke 的模型启用 image input，MiMo Pro 禁用；未列出的模型拒绝选择。复用现有附件结构、剪贴板和存储，序列化为 Responses `input_text` + `input_image`（`image_url` 为 base64 data URL）。Kimi 不发送远程 HTTP 图片 URL。只发送该 provider 接受的 detail 等可选字段。

第一版使用保守的应用限制：PNG/JPEG/WebP/GIF，单图最多 10 MiB、每轮最多 8 图、完整编码后的请求体最多 32 MiB；同时取 provider 文档限制中的更小值。粘贴校验与发送前最终校验均适用，完整请求体校验包含历史图片。DeepSeek 官方当前 inline 单图限制 32 MiB，并不意味着可以保留旧应用的 50 MiB 上限。不自动缩图、不静默截断或丢弃附件。

发送前重新核验当前模型能力。切换到 MiMo Pro 后，已有图片草稿保留，但提交被可恢复提示阻止，用户可移除附件或切回支持图片的模型。若会话重放仍包含历史图片，阻止该不兼容请求并提示切回支持模型或开始纯文本会话；不在背后删图、不将原图伪装成文字描述。已压缩且仅余摘要的上下文可按普通文本处理，原附件记录仍保存。工具返回的图片也走相同能力与大小校验，不能通过工具结果绕过限制；错误继续现有恢复路径。

附件持久化、恢复、压缩与 transcript redaction 复用现有合约；新增跨 provider 重放测试，包括切换后不透明 reasoning 的隔离。音视频/PDF 的 provider 全模态宣传不作为本次 Responses 能力开关。

### 5. 辅助模型与 usage 归属

输入建议固定使用当前 provider 的轻量模型：DeepSeek `deepseek-flash` + none，MiMo `mimo-v2.5` + disabled，Kimi `kimi-k3` + low，CLI `gpt-5.6-luna` + none。Kimi 不承诺完全关闭推理。建议不依赖其他 provider key；保持原有启用开关、超时/取消、质量过滤与独立 usage bucket。摘要和压缩使用当前会话模型与设置，维持 DeepSeek cache prefix 与 auxiliary folding 合约，但依据最终 Responses 请求校验。

subagent 未指定 model 时继承当前已构建 model；指定时在当前 provider 的目录内解析并再次构建 Responses model，不能直接把字符串交给 SDK 默认 provider。跨 provider subagent 配置不在本次范围；越界型号给出诊断。

搜索以 `purpose=web_search`、`provider=deepseek`、`model=deepseek-flash` 单独记录真实 token usage/cache usage 和 server search request 次数。session 累计包含该消耗且只计一次；当前主模型 Context Window checkpoint 不增加搜索侧 tokens。输入建议、压缩、subagent 既有分类继续保留。未知 usage 显示未知，不用零伪造；余额仍只按官方 DeepSeek 身份展示，不把 DeepSeek 搜索余额当成 MiMo/Kimi/CLI 对话账户余额。

## Risks / Trade-offs

- [模型别名、代理账号和网关能力会变化] → 发布前按九个目录模型做文本与工具 smoke、八个图片模型做图片 smoke；不得仅依据 `/models` 或 200 认定成功。新增模型须更新能力目录与证据。
- [直连 HTTP 成功不保证 SDK 多轮兼容] → 先验证 SDK 请求快照、真实 function 两轮、reasoning 重放、stream 完成/中断，再接 UI。失败时修正 adapter 或 proposal，不暗中退回 Chat Completions。
- [搜索请求可能使用数万输入 tokens] → max_uses、输出和超时有界；展示独立 usage；不自动重复付费请求、不携带完整会话。已测单次调用不是低费用保证。
- [profiles 格式是 breaking change] → 旧文件不静默迁移/覆盖，错误说明和双语手动重配步骤；所有常规更新覆盖保留其他 profile 的回归测试。
- [文本模型无法接收旧图片历史] → 显式阻止不兼容提交并保留原附件，避免丢数据和服务端不可解释失败。
- [过时 canonical Purpose 仍写 Chat Completions] → 实现归档后同步检查相关 Purpose；proposal 阶段不提前将 canonical spec 改成未实现行为。

## Migration Plan

1. 按 tasks 完成 profiles、目录与离线回归，再接 Responses、搜索和两套 UI；不修改用户实际配置或密钥用于测试。
2. 将本次调研请求做成 opt-in smoke 工具，仅从环境读取凭据；输出脱敏结果与真实能力证据，不写 provider 响应中的秘密或大块图片。
3. 通过 focused tests、全部项目质量门禁和 strict OpenSpec 验证；同步中英文升级与限制说明后再将新行为交付。
4. 用户主动重建 v2 profiles；未配置 provider 可后续添加，切换不覆盖已配置服务。CLI Proxy token 不硬编码在程序、示例或测试 fixture 中。
5. 若需回滚，恢复旧程序版本并由用户恢复其自行保留的旧配置；不让旧程序自动读取 v2 或降级重写密钥。归档只在实现和验证完成后执行，本阶段保留 active change。
