## 1. 目录与协议边界

- [x] 1.1 更新四个 provider、九个模型、显示名、默认 URL/model 与图片能力目录，移除 OpenRouter/旧 ID；用 catalog 参数化测试验证有效组合、默认值与无效选择拒绝。
- [x] 1.2 对照官方 Responses 文档和当前环境验证各模型 reasoning、tool_choice、summary 及图片限制，固定 adapter 能力表；交付脱敏请求证据，CLI effort 不支持项不得进入 picker。
- [x] 1.3 盘点主 agent、subagent、suggestion、compact/fold、doctor 的模型调用入口与旧 chat/search 路径；交付调用清单并将每个入口映射到后续测试，确认没有隐藏的 Chat Completions 调用。

## 2. Provider profiles 与凭据

- [x] 2.1 实现 v2 TOML profiles 和 active_provider 解析、模型/推理校验及旧格式诊断；用临时配置测试默认值、旧 `[model]`、旧 provider ID 和未知版本，验证拒绝时原文件不变。
- [x] 2.2 实现 provider 环境变量、Kimi 别名、空值与保存 key 的优先级；回归测试四个 profile 的 key 不串用、DEEPY_API_KEY 不跨 provider 覆盖及环境密钥不落盘。
- [x] 2.3 实现按字段合并与原子私有写入，区分 profile 编辑和 full reset；回归测试 DeepSeek→MiMo→Kimi→CLI→DeepSeek 后 key/model/URL/reasoning 均恢复，其他配置保持不变，取消/写入失败不改变运行时与磁盘状态。
- [x] 2.4 更新 setup/init/show/json 的 profiles 读写、空密码保留和全部密钥脱敏；CLI 测试覆盖新建、重复编辑、缺少活动 key、仅缺少搜索 key、未知配置路径和文件权限。

## 3. Responses 模型适配

- [x] 3.1 将 provider 构建统一到 Responses 并拆出必要小型 adapter，移除 Chat Completions wrapper/旧 reasoning replay；请求快照验证四类 provider 的 URL、model、凭据隔离、store=false、usage 和 reasoning 参数。
- [x] 3.2 适配 function schema、call ID、function output、reasoning items 和本地历史重放；参数化 SDK 两轮工具测试覆盖全部 provider，验证 MiMo nullable 默认值和伪工具调用文本不执行。
- [x] 3.3 适配流式 text/reasoning/tool/usage、失败与取消；流式 fixture 测试验证 transcript 顺序、usage 只记一次、部分响应不误标完成及 UI 可恢复。
- [x] 3.4 将输入建议改为 provider 内固定 Responses 模型与推理设置；测试 provider 切换、Kimi low、实际 usage 标签、取消/过滤与无额外 provider key 依赖。
- [x] 3.5 将 compaction/folding 和 doctor 使用同一构建路径；测试摘要使用活动模型设置、DeepSeek cache prefix/request-shape 诊断仍脱敏且基于 Responses，doctor 不再显示旧 Chat Completions 状态。
- [x] 3.6 将 subagent 显式模型覆盖解析为活动 provider 内 Responses model；测试继承、有效覆盖、跨 provider/未知型号拒绝和工具/MCP/审计边界不变。

## 4. DeepSeek 独立联网

- [x] 4.1 实现独立 Messages HTTP search adapter 与 DeepSeek 专属 key 解析，按设计设置固定 endpoint/model/tool/上限；请求 fixture 验证非 DeepSeek 活动配置不影响搜索 URL、key 或 model。
- [x] 4.2 实现关联 server_tool_use/result 的结构化解析；测试真实结果、去重来源、空结果、缺少搜索记录、只有模型 prose、工具错误、部分/截断结果及 encrypted content 不泄露。
- [x] 4.3 将 adapter 接入现有 WebSearch FunctionTool，保留 MCP-first 与 subagent search 继承；集成测试覆盖所有聊天 provider 调用该工具、Tavily 优先/失败后使用内置搜索，以及缺少 DeepSeek key 时其他能力继续可用。
- [x] 4.4 实现超时、取消、来源上限及不自动重试；确定性测试确认取消会停止待处理请求、失败不触发旧后端、不把来源裁剪当作上游 usage 减少。
- [x] 4.5 删除 SearXNG、DuckDuckGo、旧查询预处理及专用配置/依赖/提示词；静态审查活动代码与文档无旧调用入口，并运行现有 WebFetch 可读提取测试确认本地抓取保持有效。
- [x] 4.6 添加独立搜索 usage/request-count 归属和展示；测试 MiMo 对话+DeepSeek 搜索、subagent 搜索、未知 usage 与 session 总量，确认无重复累计且主模型 Context Window 不被搜索侧 tokens 更新。

## 5. 图片输入与会话

- [x] 5.1 用统一目录替换分散图片白名单，启用八个图片模型并禁用 MiMo Pro；测试所有九个组合和不支持音频/视频/PDF 的能力展示。
- [x] 5.2 实现 Responses input_text/input_image 规范化、data URL、顺序及 image-only 默认提示；请求测试覆盖 DeepSeek/MiMo/Kimi/CLI、Kimi 无 HTTP 图片 URL、文本输入与 provider 错误恢复。
- [x] 5.3 在粘贴与发送前校验 MIME、单图/数量/编码后完整请求大小和 provider 更小上限；边界测试包含历史图片、超限后保留草稿、切换 MiMo Pro 后阻止提交且不丢附件。
- [x] 5.4 将 Read 图片结果接入同一 Responses 能力与限制校验；测试真实工具结果后续模型请求、纯文本模型错误和图像大小错误，确保不会绕过校验。
- [x] 5.5 更新会话图片重放、恢复与压缩：不支持模型时显式阻止原图历史请求，文本摘要可继续；回归测试附件原件保留、跨 provider 重放合法、preview/transcript 不显示 base64。

## 6. Classic 与 Modern UI

- [x] 6.1 更新共享 picker、classic /model 命令及配置流程；交互测试验证四个 provider、有效模型/推理/图片标签、profile 恢复、空密码保留、取消与保存失败行为。
- [x] 6.2 更新 modern picker/config/reset 表单及状态文案；UI 测试验证与 classic 相同的 profiles 语义、当前会话即时刷新及 ordinary edit 不等于 full reset。
- [x] 6.3 验证两套 UI 的多图、仅图片、删除附件、粘贴拒绝、模型切换阻止提交和搜索错误展示；交付 focused UI 测试结果及人工可复现的检查步骤。

## 7. 文档与集成验收

- [x] 7.1 同步中英文 README、配置/provider、工具/MCP、图片/UI 文档与当前示例；文档检查覆盖精确 ID、Responses/搜索例外、环境变量、破坏性升级说明、图片限制、有效链接和无真实 key/token。
- [x] 7.2 提供 opt-in live smoke 工具，仅读取环境凭据并生成脱敏结果；验证九个模型文本、SDK function 两轮和流式，八个模型图片及 MiMo Pro 拒绝，不以 HTTP 200 或模型自述替代能力证据。
- [x] 7.3 使用 opt-in smoke 验证任意聊天 provider 经 FunctionTool 调用 DeepSeek Messages 搜索，核验真实搜索 block、来源和 usage；复核不支持 native web_fetch 的结论，测试结束不修改用户配置。
- [x] 7.4 对本 change 每条新增/修改 requirement 建立测试或明确验证证据映射，并先跑受影响区域 `uv run pytest <focused paths>`；验收覆盖配置、provider、tools、图片/session、subagent、建议及双 UI。
- [x] 7.5 完成集成后运行 `uv run ruff check src tests`、`uv run ty check src`、`uv run pytest` 和 `openspec validate modernize-providers-and-web --type change --strict`；所有失败修复后记录结果，不能用早期直连 smoke 代替完整门禁。
- [x] 7.6 在实现及全部验证完成后按项目流程归档并运行 `openspec validate --specs --strict`，检查最终 canonical requirement 与 Purpose 不再承诺旧 transport/provider/search；本项不授权版本发布或 Git 推送。
