## Context

见 proposal.md 的问题说明。当前 ContextConfig.window_tokens 默认为 1,048,576；UI、status 和压缩共同读取该值。ensure_context_ready 在有 usage 时优先采用旧 checkpoint，可能忽略新增输入。token 估算共用 cl100k_base，图片使用固定估算，不能作为各 provider 的精确计数。Responses 边界已有图片校验和部分 reasoning 隔离；会话存储已有事务、压缩归档和恢复设施。

当前基线已提交为 `1e0eee6`，包括 provider/Responses/search 改造及两个 Read 修复。新实现应基于这批合约，不改回旧 provider/API。

## Goals / Non-Goals

**Goals:** 为每次实际请求形成一致且可解释的预算；切换模型仍延续原任务和会话；任何失败都保留历史、附件和待发送输入；对未确认限制诚实标注。

**Non-Goals:** 不进行计费规模的百万 token 压测；不自动探测并扩大代理上限；不改变 provider 或模型目录、thinking 档位和固定建议模型；不将搜索侧 tokens 混入主上下文；不跨未配置 provider 自动调用摘要；不重写存储引擎。

## Decisions

### 1. 区分官方规格、运行上限与输出预算

为目录模型记录带来源的 ModelLimits，包含 provider/model/API、官方标称窗口、已确认精确窗口（可空）、保守运行窗口、最大输出、确认日期及限制关系。运行时生成 ResolvedModelLimits，并携带来源 official/conservative/user-cap/proxy-unverified。

2026-09-15 查证的起点：

| Provider/model | 官方窗口 | 官方输出限制 | 初始窗口政策 |
|---|---|---|---|
| deepseek/deepseek-flash | 1M | 384K | 精确含义未确认时采用 1,000,000 保守值并标注 |
| mimo/mimo-v2.5 | 1M | 128K | 同上 |
| mimo/mimo-v2.5-pro | 1M | 128K | 同上 |
| kimi/kimi-k3 | 1M | Responses max_output_tokens 最大 1,048,576，默认 131,072 | 1,000,000 保守值；输出参数最大值不作为上下文窗口证据 |
| cli_proxy/gpt-6-astra | 1,050,000 | 128,000 | 官方参考，代理未验证 |
| cli_proxy/gpt-5.6-sol | 1,050,000 | 128,000 | 同上 |
| cli_proxy/gpt-5.6-terra | 1,050,000 | 128,000 | 同上 |
| cli_proxy/gpt-5.6-luna | 1,050,000 | 128,000 | 同上 |
| cli_proxy/gpt-5.5 | 1,050,000 | 128,000 | 同上 |

来源：[DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/)、[MiMo](https://mimo.mi.com/docs/zh-CN/quick-start/summary/model)、[Kimi 模型](https://platform.kimi.com/docs/models)、[Kimi Responses](https://platform.kimi.com/docs/api/responses)、OpenAI [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)、[Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)、[Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)、[Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)、[5.5](https://developers.openai.com/api/docs/models/gpt-5.5)。本机 CLI Proxy `/v1/models` 仅返回 id/owner/created，没有窗口元数据。以上是文档证据，不是极限请求成功证据。

实现先复核精确 token 单位及输入输出是否共享窗口；不能确认时执行保守共享窗口政策，标为估算/未验证，不用猜测更新官方字段。相比统一 1,048,576，保守值不会因二进制单位假设额外放宽请求。

### 2. 配置覆盖是缩小上限

新增 `[providers.<provider>.model_limits.<model>]`：`context_window_tokens` 为选填窗口上限，`max_output_tokens` 为选填单次主/子代理请求预算。未知模型、非正整数、超过目录已知上限、输出加余量无法容纳的配置报错且不写入。

全局 `[context].window_tokens` 未写时自动跟随模型；显式写入时继续作为所有模型的安全上限，不自动迁移或复制到各 profile。有效窗口为目录运行值、全局显式上限、模型显式上限的最小值。删除覆盖即可恢复模型默认。`config show` 区分原始覆盖和解析值，不能把解析值写回并意外固定窗口。

保留 `compact_trigger_ratio` 默认 0.8，`reserved_context_tokens` 默认 50,000 作为总预留下限。主/子代理输出预算默认建议 32,768，限制为目录上限以内；摘要预算至多 8,192；建议保持 2,048。输出预算均显式传给 Responses。若小窗口连默认预算和余量都不能容纳，要求显式降低输出预算，不静默改大窗口。

### 3. 预算面向最终请求，预留只计算一次

以 target provider/model/API、history revision/projection、system/tool prefix fingerprint 标识 checkpoint。仅匹配的 checkpoint 可以用于历史估计校准；模型、端点、历史视图或前缀改变时，不复用旧精确标签。

准备目标请求视图后计算 I（完整输入）；包含系统提示、SDK 实际工具 schema、MCP 定义、历史、当前输入以及每轮新增工具结果。图片与 Read follow-up 按传输后的形态估算，不能把 base64 字符串当自然语言计数。没有 provider 专用计数时明确使用估算，不宣称精确 tokenizer 一致性。

设 W 为有效窗口、O 为此次输出预算、S 为估算余量（初始 4,096）、R 为 `max(reserved_context_tokens, O + S)`。当 `I >= ceil(W * ratio)` 或 `I + R >= W` 时准备压缩；R 已含输出，不再重复加 O。压缩后必须再次验证 `I + R < W`。已知 provider 若独立限制输入/输出，增加对应检查；不靠独立输出上限允许请求越过保守总预算。

旧 checkpoint 的历史输入与新消息必须有明确覆盖边界，避免漏加或重复加。新 usage 替换相应请求 checkpoint，不把累计消耗、搜索、建议用量或 reasoning 明细重复相加。每轮工具续接也检查预算；不能只在用户按 Enter 时检查。预算不足时在合法工具轮边界进行有界压缩，或停止并保留已执行工具结果，不自动重做工具副作用。

### 4. 原始记录与可重放视图分离

复用现有归档/事务设施，新增必要的 history projection 元数据，不引入第二套独立历史引擎。原始消息及图片原件保留；活动视图可以引用原始条目或压缩摘要。记录源 revision、目标身份、adapter 版本、摘要模型、覆盖范围、最近上下文与 tool-call 组边界。

切换保留 session ID。基础投影保留用户消息、最终回答、工具参数和结果；仅保留目标能消费的 reasoning，外部签名/加密内容不透传。同 provider 不代表跨模型 opaque reasoning 必然兼容；按来源身份和能力判定，不能只比较 provider 字符串。所有响应条目记录来源；跨来源或未知来源的服务端 item ID 在重放副本中移除（不同 provider 的 ID 格式不兼容），工具 call_id 保持不变。缺失 provenance 的不透明内容默认不传；必要推理内容无法合法恢复时使用明确文本摘要或阻止请求，不伪造 assistant/tool 项。

工具调用及结果保持有序完整组。未完成工具、审批、流式生成和活跃子代理期间，拒绝本次切换并提示完成或取消后重试，旧设置不变；不偷偷排队在用户稍后无感切换。摘要生成不执行任何历史工具。

### 5. 超限迁移要保证摘要也能装下

优先在目标模型预算内分块摘要，分块按完整消息/工具组，合并时也检查预算。如果单组或历史图片目标无法消费，可使用当前会话最后成功使用且仍配置可用的源模型生成摘要；开始前明确显示所用 provider/model 和独立摘要用量，不使用其他账户兜底。图片转文本需要显式用户选择，默认阻止；明确提供 `/compact --for-model`，目标为当前选择的模型，作为图片历史转文本的显式选择；原 `/compact [focus]` 行为继续有效，只有精确匹配该选项才走目标视图准备。

Kimi Responses 仅接受 auto tool_choice，摘要不注册工具/MCP；其他 provider 的摘要禁用工具调用。摘要保留任务目标、用户约束、未完成工作、关键工具结果与引用，说明图像仅有文字摘要及信息损失。单个不可分割组超过所有可用摘要模型预算时停止并给出诊断，不截断后谎称完整保留。

有界计划：单次准备最多 32 个摘要请求，每个请求 60 秒，可取消；超限停止，保留原件和已有有效活动视图。任一成功付费摘要请求立即记录 usage，即使最终迁移失败。只有全体摘要完成且目标预检通过、source revision 仍匹配时才事务性提交新活动视图。版本变化则丢弃待提交视图并提示重试；失败或进程中断不替换当前视图。

### 6. 选择与准备状态清楚区分

在空闲边界保存模型选择，标记目标上下文待检查；下次发送前完成准备，不在浏览 picker 时产生收费摘要。迁移失败时保留所选目标、原始历史和草稿，明确显示未就绪，允许重试或切回旧模型。取消 picker 不保存任何设置；取消迁移不发送目标请求。

切回模型只复用 revision、prefix 和预算仍有效的投影，否则重新准备。重启/resume 读取保存的视图和来源，但不能把旧目标 checkpoint 当新目标精确数据。两套 UI 显示有效窗口与来源；切换后显示目标投影估算，收到目标 usage 后才显示已报告占用。保持单一 ctx 区域，不额外增加第二个压力计数。

## Risks / Trade-offs

- [标称 1M 和代理限制不精确] → 保守值、来源状态、仅缩小覆盖；不得把短请求成功或 `/models` 当极限证据。
- [跨 tokenizer 和图片估算偏差] → 对实际请求结构估算、独立余量、真实 usage 校准和可恢复超限错误；不承诺绝不发生上游超限。
- [摘要丢失细节] → 原件可恢复、摘要有覆盖范围、保留最近完整工具组；图像降级须明确选择。
- [迁移收费/取消] → 提示摘要模型、限制次数和时间、逐请求记账；不自动反复重试。
- [并发 history 变更] → revision 校验与事务提交，失败不覆盖历史；活跃工具期间不切换。
- [既有大模块] → 抽取 limits resolver、request budget 和 replay projection，runner/UI 只做窄集成。

## Migration Plan

1. 先补目录证据和确定性预算测试，再接配置解析；不改变当前用户配置文件。
2. 存储变更使用可重复执行的增量迁移；旧 checkpoint 缺少来源时降级为估算，旧消息和归档仍可读。
3. 加入请求预算、合法投影和事务摘要，再接双 UI 与双语文档。
4. 通过 focused/full tests、Ruff、ty、strict OpenSpec。live 验证只用明确 opt-in、小规模请求；代理极限保持未验证。
5. 回退保留原始消息和已提交视图，禁止自动删除新增记录；本阶段不发布、不归档。

摘要字节预算使用 UTF-8 JSON 序列化的输入、共享摘要 instructions、完整工具定义和 MCP 快照，并预留 64 KiB SDK envelope/schema 序列化余量。快照与运行时工具同时存在时保守计入两者；最终 HTTP hook 继续验证实际请求体。

图片分批摘要后，如果文本结果已经满足下一次请求预算，即使 token 估算高于原图片估算也允许进入合并阶段；仅对仍超限且 token 没有减少的结果触发无进展保护。
