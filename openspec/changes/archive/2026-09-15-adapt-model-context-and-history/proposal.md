## Why

Deepy 已完成 provider/Responses 适配，但上下文窗口仍统一使用固定默认值，且已有 usage 时可能漏算新输入。模型切换继续使用同一会话的 history，必须同时处理目标模型的窗口、工具历史、图片能力及 reasoning 兼容性，否则会误报上下文占用或发送无法处理的请求。

## What Changes

- 建立按 provider/model/API 解析的上下文与输出限制目录，区分官方标称值、精确数值、保守运行值及代理未验证状态。
- 默认跟随模型；保留显式全局窗口作为安全上限，并增加按 provider/model 的缩小覆盖。分离模型最大输出与单次实际输出预算。
- 统一完整请求预算：系统提示、工具/MCP 定义、历史、当前输入、工具输出和图片均纳入；修复旧 usage 遮蔽新增输入的问题。
- 模型切换保留会话 ID、原始历史、附件、待发送草稿及工具配对。根据目标模型生成可重放视图，隔离不兼容 reasoning/signature/encrypted items，不修改原件。
- 超过目标窗口时生成可恢复的压缩视图；摘要请求本身也要满足所用模型预算。图片历史切换到文本模型时默认阻止，只有明确选择文本摘要后才转换。
- 在安全边界切换模型；对失败、取消、断点恢复和并发历史变更提供明确恢复路径。切换回原模型时复用有效历史视图，不静默恢复导致超限的旧活动上下文。
- 两套 UI、status/doctor、主模型、子代理和压缩共用限制解析；跨模型旧 checkpoint 标为不适用，显示目标历史估算，后续真实 usage 再校准。

## Capabilities

### New Capabilities
- `model-context-budget`: 模型限制证据、完整请求预算、输出预留、摘要和子代理预算。
- `model-history-switch`: 保留原始历史的目标模型投影、安全切换与迁移恢复。

### Modified Capabilities
- `configuration`: 模型限制覆盖、全局窗口上限及解析后的预算显示。
- `session-context`: checkpoint 身份、完整待发送上下文与压缩视图持久化。
- `terminal-ui`: 目标模型窗口、估算状态及切换恢复提示。
- `experimental-textual-tui`: 与 Classic 一致的切换历史与预算行为。
- `user-documentation`: 双语解释模型窗口、代理限制、历史保留与恢复方式。

## Impact

涉及 config catalog/schema、Responses 请求准备、context/compaction、session store、子代理构建和双 UI。复用现有事务存储和压缩归档机制，新增聚焦的限制解析和历史投影 helper；避免继续扩张大型 runner/UI 模块。不新增 provider，不重新引入旧 API，不改变 MCP 权限，不改变输入建议的固定模型/thinking。搜索独立 usage 不进入主会话窗口。

本 change 仅提出设计与任务，不包含运行时代码实现；不授权发布或推送。
