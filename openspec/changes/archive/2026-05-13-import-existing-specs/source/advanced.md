# Deepy Python 版高级功能扩展规划

## Summary

本文记录 Deepy 迁移到 Python 之后可以继续扩展的功能方向，以及针对 DeepSeek 模型能力可以做的特色优化。核心原则是：第一阶段以核心行为兼容和 Python 化实现为主，高级功能应在 Python 版稳定后逐步加入，避免把迁移工程扩大成一次性平台重写。

## 通用扩展功能

### 1. MCP 支持

MCP 是最值得优先考虑的扩展之一。当前 Deepy 内置工具主要是 `bash`、`read`、`write`、`edit`、`AskUserQuestion`、`WebSearch`。迁到 Python 后可以接入 `fastmcp`，支持：

- `deepy mcp add/list/remove`
- 项目级 MCP 配置
- stdio/http/sse MCP server
- 将 MCP tools 和内置 tools 一起暴露给模型
- 为 MCP 工具增加 allow/block 规则和执行审计

### 2. 更强的项目索引

当前主要靠模型临时调用 `read`、`bash`、`rg` 探索项目。可以增加本地索引能力：

- 基于 `rg` 的快速文件搜索
- 代码符号索引
- 最近修改文件权重
- git diff / git status 上下文自动注入
- 语言级索引，例如 Python AST、TypeScript tsserver、Rust rust-analyzer
- 为大仓库提供轻量 cache，减少重复扫描成本

### 3. 任务计划模式 / Plan Mode

增加显式 `/plan` 模式，适合复杂任务、迁移任务和高风险修改：

- 只允许读文件、搜索、运行非破坏性命令
- 禁止 `write`、`edit` 和危险 shell 命令
- 生成 `plan.md` 或阶段性计划
- 用户确认后再进入执行模式
- 在计划阶段记录约束、成功标准、测试策略和回滚策略

### 4. 审批机制

当前工具调用偏向模型直接执行。可以增加 approval runtime：

- 写文件前显示 diff
- shell 命令分级：安全、需确认、禁止
- 支持 yolo / cautious / read-only 模式
- 支持记住某类命令的批准规则
- 对跨目录写入、删除、网络、git push 等操作强制确认

### 5. 子任务 / Subagent

Python 版可以支持轻量 subagent，用于大型代码库和复杂任务：

- explore agent：只读分析某个模块
- test agent：专门跑测试和定位失败
- review agent：审查当前 diff
- migration agent：负责某一批文件迁移
- summary agent：压缩长会话和提取关键决策

第一版不建议做完整多 agent 平台，可以先做受控的内部任务委派。

### 6. 更好的会话系统

当前会话是 JSONL + index。后续可以扩展为：

- session tag
- session search
- session branch/fork
- checkpoint/rollback
- 自动标题
- 导出 markdown/html
- 按项目查看历史任务
- 在 session list 中展示模型、token、成本、最近工具调用状态

### 7. 代码修改质量增强

可以把 `edit` 工具做得更强：

- AST-aware edit
- 自动格式化但只限修改过的文件
- 修改后自动运行相关测试
- 失败后自动回滚本轮修改
- diff review UI
- 对大文件修改要求 snippet 或结构化定位
- 记录每次工具修改的 before/after 元数据

### 8. 工作流命令

增加面向工程任务的 slash commands：

- `/test`：运行相关测试
- `/review`：审查当前 diff
- `/commit`：生成提交信息
- `/explain`：解释当前文件、错误或测试失败
- `/fix-ci`：读取 CI 日志并修复
- `/summarize`：总结当前 session
- `/config`：查看和修改当前 deepy 配置
- `/doctor`：检查 API key、模型、base_url、依赖和 shell 环境

### 9. 文档和多模态能力

Python 生态更容易扩展文档和多模态处理：

- PDF 读取
- docx/xlsx/pptx 解析
- 图片 OCR
- 截图理解
- 代码仓库文档生成
- 自动生成迁移报告
- 将工具结果导出为 markdown、HTML 或 PDF

### 10. 后台任务

支持长任务后台运行：

- 长测试
- 构建
- 大规模搜索
- 代码索引
- watch 模式
- 完成后通知
- 退出时可选择保留或清理后台任务

## 针对 DeepSeek 的特色功能

### 1. DeepSeek Thinking 控制面板

当前已有 `thinkingEnabled` 和 `reasoningEffort`。后续可以做成运行时可调：

- `/thinking on/off`
- `/effort high/max`
- 针对任务类型自动选择 effort
- 简单问题自动关闭 thinking
- 复杂重构自动打开 max
- 在 session 状态中显示本轮 thinking 设置

### 2. KV Cache 成本优化

DeepSeek 强调上下文缓存。Deepy 可以做 DeepSeek 专用 prompt 稳定化：

- 稳定 system prompt 顺序
- 稳定 tools schema 顺序
- 将不变上下文和变化上下文分层
- skills、AGENTS.md、工具文档尽量固定位置
- 减少每轮 prompt 抖动，提高 cache hit
- 显示或估算 cache 相关 token 成本变化

这是 DeepSeek 方向最有价值的差异化之一。

### 3. 上下文分层策略

针对长上下文模型做明确分层：

- 固定层：system prompt、工具说明、项目规则
- 项目层：AGENTS.md、package/pyproject、目录结构
- 会话层：用户任务、关键决策
- 动态层：当前 diff、最近错误、当前文件

这种结构既利于 DeepSeek 长上下文，也利于 KV cache。

### 4. DeepSeek 模型路由

针对 `deepseek-v4-pro` / `deepseek-v4-flash` 做自动路由：

- 快速问答、搜索、简单解释用 flash
- 复杂设计、迁移、debug 用 pro
- edit 修复失败后升级到 pro + max thinking
- summarization/标题生成用低成本模型
- 根据用户配置允许固定模型，避免自动路由造成不可预测成本

### 5. 推理内容显示优化

针对 DeepSeek reasoning/thinking 输出提供更好的终端体验：

- 默认折叠 thinking
- 显示“正在分析 / 正在定位 / 正在规划”等状态
- 可按步骤展开
- `/thinking-log` 查看本轮推理摘要
- 退出摘要中记录 thinking token/cost

UI 上更适合显示摘要和状态，不应把完整内部推理当成最终答案依据。

### 6. DeepSeek 错误适配

针对 DeepSeek API 做专门错误解释：

- context overflow
- thinking 参数不兼容
- rate limit
- base_url 配错
- model 名错误
- API key 缺失或无权限
- OpenAI-compatible 字段差异

用户看到的应是可行动修复建议，而不是裸 HTTP 错误。

### 7. 上下文压缩专门优化

当前已有 compaction。DeepSeek 版可以增强为：

- 保留工具调用结果的结构化摘要
- 保留用户约束和决策
- 保留文件路径和行号
- 压缩前后显示 token 节省
- 对 DeepSeek 长上下文阈值使用更高默认值
- 避免压缩固定 prompt 层，减少 cache 失效

### 8. Skills 自动匹配增强

当前已有 skills 自动匹配。可以继续优化：

- 使用便宜模型先做 skill routing
- skill 内容延迟加载
- skill 摘要先加载，必要时再全文加载
- skill 与工具权限绑定
- 为 DeepSeek prompt 缓存保持 skill 注入顺序稳定

### 9. 中文工程体验优化

DeepSeek 用户中中文场景较多，可以增强中文工程体验：

- 中文错误解释
- 中文 commit message 模板
- 中文代码审查模式
- 中英文混合搜索 query 自动改写
- 技术术语保留英文、解释用中文
- 对中文 README、需求文档、接口文档做更好的摘要和生成

### 10. DeepSeek Coding Plan 模式

可以做一个明确面向 DeepSeek/Coding Plan 类模型的模式：

- `/coding-plan`
- 自动启用 thinking
- 自动生成阶段计划
- 每阶段执行前确认
- 每阶段结束总结上下文
- 失败时回到计划修订
- 将 plan、执行记录、测试结果写入 session 元数据

## 建议优先级

第一批最值得做：

1. Plan Mode：读写权限分离，和 agent CLI 强相关。
2. DeepSeek KV Cache 优化：这是 DeepSeek 专属价值。
3. MCP：扩展工具生态。
4. 更好的 session/search/fork：让长期使用更舒服。
5. DeepSeek 模型路由：降低成本，提高响应速度。

不建议第一阶段就做：

- 完整 subagent 平台
- 复杂 Web UI
- 大规模 SQLite 迁移
- OAuth 多提供商
- 过度复杂的插件系统

这些会把迁移工程变成重写平台，风险太高。更稳妥的路径是：先完成 Python 核心能力迁移和必要兼容，再按优先级逐步扩展高级能力。
