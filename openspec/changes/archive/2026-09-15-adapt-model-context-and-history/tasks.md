## 1. 模型限制与配置

- [x] 1.1 复核九模型的官方上下文、输出参数、单位和输入输出限制关系，交付带日期/链接的证据表；保留 1M 保守值和 CLI Proxy 未验证标签，不用短请求代替上限证据。
- [x] 1.2 建立聚焦的模型限制目录与 resolver；参数化测试九模型默认值、标称/精确/保守值区别及有效窗口取最小值。
- [x] 1.3 实现 provider/model 覆盖和显式全局窗口上限；测试缺省自动跟随、切换恢复、非法值拒绝、空配置及其他 profile 不变。
- [x] 1.4 更新 config show/json/doctor 的解析值与来源展示；测试密钥脱敏、代理未验证标签、读取不落盘及原子写入失败。

## 2. 完整请求预算

- [x] 2.1 抽取完整请求预算计算，覆盖 system/tool/MCP/history/new input/Read 图片；测试新增内容不会被旧 checkpoint 遮蔽、base64 不按普通文本计数及跨 tokenizer 估算标签。
- [x] 2.2 加入单次输出预算和总 reserve 计算；请求快照验证主模型默认 32768、摘要至多 8192、建议 2048 及模型限制，边界测试确保不重复预留输出。
- [x] 2.3 接入主请求和每轮 function continuation 的预检；SDK 多轮测试覆盖工具结果导致超限、合法停止/压缩和工具副作用不重复。
- [x] 2.4 让子代理显式模型覆盖及压缩使用各自有效限制；测试父子不同模型、不同输出预算及搜索/建议 usage 不更新主窗口。

## 3. History 与 checkpoint

- [x] 3.1 增量持久化 checkpoint 身份和 history projection 元数据，复用现有事务/归档；测试旧数据库可读、旧无来源 checkpoint 降级及迁移幂等。
- [x] 3.2 构建目标模型合法重放视图；测试跨 provider、同 provider 跨 model、缺 provenance、opaque reasoning 隔离和原始消息不变。
- [x] 3.3 保留完整工具调用/结果组及顺序；测试多工具并行配对、未完成组诊断、压缩边界不截断调用组及无伪造结果。
- [x] 3.4 实现模型切换和 resume 后预算重新解析、视图缓存失效；测试大窗口到小窗口、切回、前缀变化、新消息追加及旧 usage 不作为目标精确占用。

## 4. 有界迁移与恢复

- [x] 4.1 实现按目标预算分组摘要与合并，必要时仅使用会话最后成功且可用的源模型；请求测试确认摘要本身不超限、使用模型可见、不调用无关 provider。
- [x] 4.2 实现 /compact --for-model 的图片转文本显式路径；测试默认阻止、明确选择后摘要、无可用图片模型时保留原件、旧 /compact focus 行为不变。
- [x] 4.3 实现有界摘要计划、逐请求 usage 和取消；确定性测试覆盖 32 次上限、60 秒请求超时、部分成功后失败与不自动重复收费请求。
- [x] 4.4 实现 revision 校验和活动视图事务提交；故障注入测试验证失败、进程中断、并发追加后不会提交半成品，原件/草稿可恢复。

## 5. 双 UI 与文档

- [x] 5.1 接入 Classic 安全切换及 ctx 显示；交互测试覆盖活跃工具/审批/子代理拒绝切换、空闲选择、目标估算标签、待准备和失败恢复。
- [x] 5.2 接入 Modern 相同流程；UI 测试覆盖切换后历史和附件保留、取消不丢草稿、/compact --for-model 及收到目标 usage 后更新。
- [x] 5.3 同步中英文 README/context/provider 文档；检查覆盖公式、窗口来源、CLI Proxy 上限覆盖、历史不丢失、图像摘要损失和用量语义。

## 6. 集成验收

- [x] 6.1 建立每条 requirement 的测试/证据映射，运行 config/llm/session/subagent/UI 的 focused tests；补齐已有 canonical compaction/cache 合约回归。
- [x] 6.2 提供 opt-in 小规模模型切换烟测并记录实际范围；验证正常历史/工具/图片路径，不发送百万 token 压测，不把代理极限标为已实测。
- [x] 6.3 运行 uv run ruff check src tests、uv run ty check src、uv run pytest、openspec validate adapt-model-context-and-history --type change --strict；记录完整通过结果后才申请归档，本项不包含发布或推送。

- [x] 6.4 修复 schema 联合类型导致预算计算崩溃的问题；验证完整 Deepy 工具集下九模型流式 hi 请求，并重跑质量门禁。

- [x] 6.5 精简双 UI 的 ctx 状态：K/M 数字、符号标记估算/保守/代理和压缩提示，详细信息留在 status/doctor；同步文档与测试。

- [x] 6.6 修复摘要分组的编码字节预算，覆盖图片、系统/工具前缀和 focus/todo；验证大图片分批、不可拆组拒绝，并重新审查与运行门禁。

### 6.6 验证结果

- 摘要大小与历史压缩 focused tests（含 JSON 约定）：33 passed。
- 最终完整套件：1102 passed；通过临时 Path.home 隔离沙箱外的 session 写入。
- Ruff、ty、OpenSpec strict validation、git diff --check 通过。
- 重新审查未提交差异，未发现新的可操作问题；未调用真实 provider API。
