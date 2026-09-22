# 模型上下文与切换

Deepy 按所选 provider/model 解析窗口和输出预算。不写 `context.window_tokens`
时跟随模型；显式值是全局安全上限，不会放宽模型运行上限。
`deepy config show --json` 和 `deepy doctor` 展示解析值及来源；读取和展示不会把推断值写回配置。

## 2026-09-15 查证的限制

MiMo 限制于 2026-09-22 更新，其他条目保留 2026-09-15 的证据。MiMo 输出上限来自接口文档明确值，未进行极限容量实测。

| Provider/model | 官方窗口 | 运行窗口 | 采用的输出上限 | 证据 |
| --- | --- | --- | --- | --- |
| DeepSeek / deepseek-flash | 1M | 1,000,000 | 384,000（384K 保守值） | [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/) |
| MiMo / mimo-v2.6-flash | 1M | 1,000,000 | 131,072（文档明确值） | [MiMo](https://mimo.mi.com/docs/zh-CN/api/chat/responses) |
| MiMo / mimo-v2.6-pro | 1M | 1,000,000 | 131,072（文档明确值） | [MiMo](https://mimo.mi.com/docs/zh-CN/api/chat/responses) |
| Kimi / kimi-k3 | 1M | 1,000,000 | 输出参数上限 1,048,576 | [模型](https://platform.kimi.com/docs/models)、[Responses](https://platform.kimi.com/docs/api/responses) |
| CLI Proxy / gpt-6-astra | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-6-astra) |
| CLI Proxy / gpt-5.6-sol | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.6-sol) |
| CLI Proxy / gpt-5.6-terra | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.6-terra) |
| CLI Proxy / gpt-5.6-luna | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.6-luna) |
| CLI Proxy / gpt-5.5 | 1,050,000 | 1,050,000 | 128,000 | [OpenAI](https://developers.openai.com/api/docs/models/gpt-5.5) |

标称 1M 不能证明二进制单位，因此标为 `conservative`，官方精确 token 数保持未知。
CLI Proxy 使用 OpenAI 参考规格并标为 `proxy-unverified`；`/models` 没有部署限制信息，
短请求成功也不证明极限窗口。Kimi 输出参数独立于输入长度，不能据此放宽上下文。
尚未确认输入输出共享关系时，Deepy 保守地将两者合计预算；这是客户端策略，不是新的厂商承诺。

## 缩小窗口与输出预算

TOML 中包含点号的 model ID 必须加引号：

```toml
[context]
# 可选的全局上限；省略时跟随所选模型。
# window_tokens = 900000
compact_trigger_ratio = 0.8
reserved_context_tokens = 50000

[providers.cli_proxy.model_limits."gpt-5.6-terra"]
context_window_tokens = 128000
max_output_tokens = 16384
```

有效窗口取目录、全局显式上限和模型上限的最小值。`max_output_tokens` 是单次请求预算，
不等于模型物理上限。主模型与子代理默认 32,768；摘要至多 8,192；输入建议仍为 2,048，
其固定模型和 thinking 不变。非法值、未知模型、超上限或容不下输出及预留的配置在保存前拒绝。
其他 provider 配置与密钥不受影响；删除覆盖后恢复模型默认值。

令 I 为完整输入估算，W 为窗口，O 为请求输出预算，R = max(reserved_context_tokens, O + 4096)。
当 I >= ceil(W × compact_trigger_ratio) 或 I + R >= W 时准备压缩；发送前要求 I + R < W。
输出仅预留一次。系统提示、实际工具/MCP schema、历史、新输入、工具结果和标准化图片都计入 I；
base64 不按普通文本计数。tokenizer 与图片计数为估算，匹配身份的 usage checkpoint 用于校准历史，
不会遮蔽新增输入。搜索和建议用量不进入会话窗口；成功摘要即记账，即使后续迁移失败。

## History 与恢复

`/model` 保留会话和原始消息。生成、工具、审批或子代理未结束时拒绝切换；空闲时保存选择，
下次发送前准备历史，浏览 picker 不产生摘要调用。单一 `ctx` 区域显示目标窗口、来源和估算状态，
收到匹配 usage 后才显示已报告占用。跨 provider、模型或端点的 reasoning 不进入目标重放视图，
原始记录和完整工具调用/结果组仍保留。resume 和切回模型都会重新校验当前预算与前缀。

图片历史切换到纯文本目标时，可切回图片模型、创建纯文本会话，或明确执行 `/compact --for-model`。
该命令允许生成可能丢失图像细节的文字摘要，仅使用会话最后成功且仍可用的图片源模型。
调用前显示模型身份，不会自动选择无关账户。原件保留在会话现有 SQLite 归档中。
原 `/compact [focus]` 用法继续可用。

摘要只在完整历史/工具组边界分块，每次摘要和合并都按其模型预算检查。
单次准备最多 32 个请求、每个请求至多 60 秒，可取消。失败、取消、历史版本变化或单组超限时，
停止准备并保留旧活动视图、草稿和附件；全部检查通过后才事务提交。
工具续接超限时在下一次 HTTP 请求前停止，保留已执行结果，不会自动重复工具副作用。

`scripts/smoke_model_history.py` 是显式启用的小规模烟测，使用临时会话、标准密钥环境变量，
检查文本/工具历史和图片请求；不测量极限上下文，不修改用户配置，也不认证代理部署上限。

底栏示例：`ctx 12.5K/1M~ (1.3%)`。用量前的 `~` 表示估算；窗口后的 `~` 表示保守上限，`?` 表示代理上限未验证；`-` 表示用量未知，末尾 `!` 表示下次请求需要压缩。底栏省略剩余 token 和状态长词，完整数字、来源与就绪状态在 `/status`、`deepy doctor` 中查看。

摘要分组同时检查 32 MiB 编码请求体上限，计入图片、摘要提示、focus/todo 和工具定义，并保留序列化余量。独立图片组会在发送前拆分；无法拆分的超大工具组会被拒绝，原历史保持完整。
