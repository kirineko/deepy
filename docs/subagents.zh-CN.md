# Deepy Subagents

Deepy 可以把独立的专项工作委派给 subagent，同时由主 agent 保留最终回答控制权。
当任务中存在可以拆开的调研、审查或验证部分时，subagent 很适合使用。

## 内置 Subagents

Deepy 会把内置 subagent 暴露为模型可调用工具：

| Subagent | 工具名 | 适合场景 |
| --- | --- | --- |
| `explore` | `subagent_explore` | 只读代码库、文档和 web/search 调研。 |
| `reviewer` | `subagent_reviewer` | 正确性、安全性、可维护性、设计和测试风险审查。 |
| `tester` | `subagent_tester` | 通过受限 `test_shell` 复现 bug 和执行验证。 |

当主 agent 判断任务足够大或足够专门化时，会自动决定是否委派。终端会显示紧凑的
`[Subagent] <name>` 生命周期行，以及最终 subagent 报告。

你也可以用 slash command 显式路由：

```text
/explore inspect the auth flow and summarize risks
/reviewer review the staged diff for regressions
/tester reproduce the failing CLI test
```

## 限制

- Subagent 不会再启动其他 subagent。
- 内置 subagent 默认没有源码修改工具。
- `tester` 收到的是 `test_shell`，不是 unrestricted `shell`。
- 当前版本不支持后台或可恢复 subagent。
- subagent 内触发的 OpenAI Agents SDK approval interruption 会冒泡到外层
  Deepy session，由用户在外层界面 approve 或 reject。

## 自定义 Subagents

项目级自定义 subagent 放在 `.deepy/subagents/*.md`。用户级自定义 subagent
放在 `~/.deepy/subagents/*.md`。项目定义会覆盖用户定义，用户定义会覆盖同名内置定义。

Deepy 不会把 `.agents/skills` 当成 subagents 加载。那个目录仍然用于 Agent Skills。

模板：

```md
---
name: triage
description: Read logs and source paths to identify likely root causes.
model: inherit
tools:
  - Search
  - read_file
  - WebFetch
mcp:
  inherit_search: false
max_turns: 20
---

You are a read-only triage subagent. Inspect only the assigned scope.
Return likely causes, evidence, relevant paths, and unresolved questions.
Do not modify files or run commands.
```

支持的 frontmatter 字段：

| 字段 | 必填 | 含义 |
| --- | --- | --- |
| `name` | 是 | 稳定 subagent 名称。同名项目/用户定义会覆盖低优先级定义。 |
| `description` | 是 | 给主 agent 判断是否委派用的简短描述。 |
| `model` | 否 | `inherit` 或其他支持的模型选择策略。 |
| `tools` | 否 | 给 subagent 的显式支持工具列表。 |
| `disallowedTools` | 否 | 从 subagent 中移除的支持工具。 |
| `mcp` | 否 | MCP 继承策略，例如 `inherit_search: false`。 |
| `max_turns` | 否 | 有界 max-turn 限制。 |

自定义 subagent 支持的工具：

- `Search`
- `read_file`
- `WebSearch`
- `WebFetch`
- `load_skill`
- `task_output`
- `test_shell`

`edit_text`、`write_file`、`apply_patch` 和 raw `shell` 这类修改工具在当前版本不支持给 subagent 使用。

## MCP 搜索继承

内置 `explore` subagent 可以继承 Deepy 识别为优先 web/search 的 MCP tools。
非搜索 MCP tools 默认不会继承。

自定义 subagent 可以关闭搜索继承：

```md
mcp:
  inherit_search: false
```

MCP 配置细节见 [mcp.zh-CN.md](mcp.zh-CN.md)。

## `test_shell`

`test_shell` 会把命令解析成 argv，不通过 unrestricted shell 执行。它会把命令分成：

- `allow`：立即执行，带有受限 timeout、固定项目 cwd、stdout、stderr、exit code、
  elapsed time 和截断元数据。
- `approval_required`：audit 启用时通过 Deepy 外层 audit approval 流程处理；没有
  active audit policy 时返回命令、原因和 approval token，用于同一命令重试。
- `deny`：拒绝 destructive、publishing、source-mutating 或不支持的命令。

支持的低风险命令族包括 Python/uv/pip 测试和检查命令、Node 包管理器 test/lint/typecheck/build
命令、Maven/Gradle test/verify/package/build、Rust `cargo test/check/clippy`、
Go `go test/vet`、只读 `curl`、`ping`、只读 `mysql`、只读 Docker/Docker Compose
诊断、`head` 和 `tail`。

需要 approval 的例子包括依赖安装、Spring Boot 服务启动、Docker Compose 启动/构建、
Rust `cargo run`，以及项目自定义的中风险模式。

拒绝的例子包括 `rm`、会修改源码的 `mv`/`cp`、`chmod`、`chown`、会修改的 git 命令、
包发布/部署、`docker system prune`、`docker compose down -v`、会修改的 `curl`、
会修改的 `mysql`，以及 pipes、separators、redirection、command substitution、
background operators 这类 shell composition。

项目策略扩展可以配置在 `~/.deepy/config.toml` 或选中的 Deepy config 文件里：

```toml
[tools.test_shell]
allow_patterns = ["make test-*", "just verify *"]
approval_required_patterns = ["make seed-db", "docker compose up *"]
```

全局 deny 规则始终高于项目 allow patterns。

## 好的自定义 Subagent 指令

自定义 subagent 指令应当保持范围清晰、基于证据：

```text
Inspect only the assigned paths.
Return findings with file paths and commands run.
Do not modify files.
Call out unresolved questions separately.
```
