# Deepy 开发规范

本文件是 Deepy 仓库的项目级开发规范，供维护者和 coding agent 共同遵守。修改代码、
OpenSpec、测试、发布文件或 GitHub Actions 前，先阅读并遵循这里的约定。

## 核心原则

- 优先做小而可审查的改动，保持现有架构边界。
- 编辑前先阅读相关代码、测试和 OpenSpec 规格。
- 不在实现当前需求时重写无关代码。
- 用户可见行为、文档、测试和 OpenSpec 合约必须同步更新。
- 所有 Python 项目命令都通过 `uv` 执行。
- 搜索仓库内容优先使用 `rg` / `rg --files`。
- 除非用户明确要求，不要回滚用户已有改动。

## OpenSpec 开发流程

Deepy 使用 OpenSpec 作为行为级变更的事实来源。

### 什么时候必须走 OpenSpec

以下变更在实现前必须创建或更新 OpenSpec change：

- CLI、TUI、terminal UI、tool、session、provider、config、MCP、subagent、skill、
  background task 等行为变化。
- 用户可见输出、prompt、slash command、快捷键、错误提示或恢复体验变化。
- 对外文档承诺、安装流程、发版流程变化。
- 跨平台运行时变化，尤其是 Windows、PowerShell、路径、编码、换行和 shell 命令语义。
- 已被 `openspec/specs/*/spec.md` 覆盖的任何行为合约。

小型内部重构、错别字、纯测试调整、机械清理，如果不改变可观察行为，可以不创建新的
OpenSpec change。无法判断时，默认走 OpenSpec。

### Proposal 阶段

行为变更先进入 proposal：

1. 用 `openspec list --specs` 查看现有规格。
2. 选择简洁的 change id，例如 `improve-tool-error-display`。
3. 在 `openspec/changes/<change-id>/` 下创建变更。
4. 提供 `proposal.md`、`tasks.md`，并在 `specs/<capability>/spec.md` 下写 delta spec。
5. 实现前先验证 proposal：

```bash
openspec validate <change-id> --type change --strict
```

### Implementation 阶段

实现过程中：

- 按 `openspec/changes/<change-id>/tasks.md` 完成任务。
- 测试应贴近被保护的行为。
- 如果实现发现 proposal 不准确，先更新 OpenSpec change，再继续写代码。
- 反复运行 scoped validation：

```bash
openspec validate <change-id> --type change --strict
```

### Archive 阶段

只有在实现和验证完成后才归档：

```bash
openspec archive <change-id> -y
openspec validate --specs --strict
```

归档后检查相关 `openspec/specs/*/spec.md`，确认最终行为合约已经同步到 canonical spec。

## 测试与质量流程

日常开发按这个顺序执行：

1. 先跑受影响区域的 focused tests。
2. 再跑项目质量门禁。
3. 发布或大范围行为变更前跑完整测试。

### 标准命令

非平凡代码改动提交前运行：

```bash
uv run ruff check src tests
uv run ty check src
uv run pytest
```

开发中的 focused loop 优先运行最小相关测试：

```bash
uv run pytest tests/tools/test_tools.py -q
uv run pytest tests/ui/classic/test_terminal.py -q
```

发布前运行完整套件：

```bash
uv run pytest -q
uv run ruff check src tests
uv run ty check src
```

涉及打包、版本或发布元数据时，还要运行：

```bash
uv build --clear
uv run deepy --version
```

## GitHub Actions 发版流程

仓库通过 GitHub Actions 发布：

- `.github/workflows/publish.yml` 在匹配 `*.*.*` 的 tag push 后发布到 PyPI。
- `.github/workflows/pages.yml` 在 `main` push 后部署 GitHub Pages。

### 发版前检查

创建 release commit 和 tag 前：

1. 确认所有相关 OpenSpec changes 已归档。
2. 运行 `openspec validate --specs --strict`。
3. 运行完整测试和质量门禁。
4. 同步更新所有版本面：
   - `pyproject.toml`
   - `src/deepy/__init__.py`
   - `uv.lock`
   - `index.html`
   - README 或 docs 中存在发版版本文本时，也必须同步
5. 运行 `uv build --clear`。
6. 运行 `uv run deepy --version` 并确认目标版本正确。
7. 创建 tag 前检查现有 tag 形式。

除非用户明确要求其他形式，默认使用裸 semantic-version tag：

```bash
git tag 0.2.22
git push origin main
git push origin 0.2.22
```

### Push 后验证

push `main` 和 tag 后验证远端引用与 Actions：

```bash
git ls-remote origin refs/heads/main refs/tags/<version>
gh run list --limit 5
gh run watch <run-id> --exit-status
```

本次 release 涉及的 workflow 都必须成功：

- release tag 触发的 `Publish to PyPI`。
- `main` push 触发的 `Deploy GitHub Pages`。

条件允许时，还要验证 PyPI 包和主页展示的版本号符合预期。

## Python 代码规范

### 基础风格

- 目标运行时为 Python 3.12 或更新版本。
- public API 和跨模块边界必须有清晰类型。
- 跨模块传递的结构化数据优先使用 dataclass、Pydantic model 或 typed dict。
- 函数保持短小，名称应直接表达行为。
- 避免用 boolean flag 参数切换复杂行为；优先拆成独立函数或小策略对象。
- 避免宽泛的 `except Exception`，除非该边界必须把未知异常转换为用户可见错误。
- 涉及 shell、路径、换行、编码的改动必须保留或新增平台语义测试。
- 注释保持克制，只解释非显然决策，不解释语法。

### 模块大小与拆分要求

新模块应当聚焦，能在一次阅读中理解。

- 新模块优先控制在 300 行以内。
- 超过 400 行视为 code review 警戒线。
- 超过 600 行的既有模块，不应继续追加大块新行为；如果必须追加，需要同步抽取聚焦的
  helper module，或在变更说明中解释为什么暂不拆分更安全。
- 不创建新的 1,000 行以上模块。

既有大模块属于遗留表面。修改这些文件时：

- 当前 diff 保持最小。
- 如果新增了有意义的行为，应识别可抽取的清晰边界。
- 优先抽取纯 helper、渲染/格式化逻辑、解析逻辑、命令 handler、平台 adapter。
- 抽取前或抽取时补上边界测试。
- 除非拆分是安全实现行为变更的前提，不要把大规模拆分和高风险行为变更混在同一个
  改动里。

推荐拆分边界：

- UI rendering 与 state transition 分离。
- shell/platform detection 与 command execution 分离。
- tool schema/argument parsing 与 tool side effect 分离。
- session persistence 与 transcript presentation 分离。
- provider request/response normalization 与 terminal display 分离。

### 测试要求

测试应覆盖行为，而不是实现细节。

- 每个 bug fix 都要补 regression test。
- 每条新的 OpenSpec requirement 都要有 focused test 覆盖。
- 大范围重构、发布工作、共享工具变更必须跑完整套件。
- 优先写确定性测试，避免依赖时序。
- 如果测试必须使用 timeout 或 sleep，时间要短，并说明原因。

## 文档规范

- README、docs、OpenSpec specs 和运行时行为必须一致。
- 修改共享用户文档时，中英文版本都要同步。
- 不记录尚未实现并测试通过的行为。
- 示例命令应简洁，并尽量可以直接复制到终端执行。

## Commit 规范

- 一个 commit 只包含相关改动。
- commit message 使用清晰的祈使句，例如 `Improve tool error display`。
- commit 前检查 `git status --short`，确保没有纳入无关用户改动。
- release commit 使用 `Release <version>`。
