<p align="center">
  <img src="https://raw.githubusercontent.com/kirineko/deepy/main/asset/deepy-logo.webp" alt="Deepy logo" width="144">
</p>

<h1 align="center">Deepy</h1>

<p align="center">
  面向 DeepSeek 的终端编程 Agent。
  <br>
  在一个可恢复的项目会话里阅读代码、修改文件、运行命令、检索网页，并管理长上下文。
</p>

<p align="center">
  <a href="https://kirineko.github.io/deepy/">项目主页</a>
  ·
  <a href="README.md">English</a>
  ·
  <a href="#快速开始">快速开始</a>
  ·
  <a href="#日常使用">日常使用</a>
</p>

![Deepy 终端启动界面](https://raw.githubusercontent.com/kirineko/deepy/main/asset/welcome.webp)

## Deepy 能做什么？

Deepy 是一个面向 DeepSeek OpenAI 兼容模型的 Python CLI 编程 Agent。它把日常
AI 编程循环放在终端里：理解项目、回答问题、修改代码、运行验证命令、搜索或抓取网页，
并在之后继续同一个项目会话。

Deepy 的设计重点是 DeepSeek V4 thinking 模式、长上下文、上下文缓存和 Rich 终端 UI。
它不会把工具调用藏在对话文本后面，而是把 thinking、文件 diff、shell 输出、usage 和
上下文状态都展示出来。

## 为什么使用 Deepy？

- **DeepSeek 优先默认值**：默认使用 `deepseek-v4-pro`，启用 thinking，并设置
  `reasoning_effort=max`；可通过 `/model` 切换 V4 Pro / V4 Flash，以及 `none`、
  `high`、`max` 三档 thinking 强度。
- **面向项目的编程工具**：读取文件、新建文件、修改文件、运行 shell 命令，并展示可读 diff。
- **可审查的终端记录**：thinking、工具调用、shell 输出、token usage、context 状态和命令结果都会显示在终端。
- **终端内资料检索**：WebSearch 用于发现资料，WebFetch 用于读取指定 URL 的正文和 metadata。
- **长会话连续性**：JSONL session、`/resume`、`/new`、Context Window 状态、自动 compact 和手动 `/compact`。
- **本地命令模式**：输入 `!cmd` 可以直接运行本地非交互命令，不经过模型，但结果仍会保存进上下文。
- **跨平台 shell 处理**：支持 POSIX shell、PowerShell、cmd、Windows 路径、UTF-8 输出、CRLF 编辑和 pywinpty 本地命令路径。

## 效果预览

### 终端里的 Agent 工作流

Deepy 会把模型 reasoning、WebFetch、shell 输出和状态行放在同一条 transcript 中。

![Deepy thinking、WebFetch 和 shell 输出](https://raw.githubusercontent.com/kirineko/deepy/main/asset/webfetch-shell-thinking.webp)

### 带 diff 的代码修改

文件修改会展示路径信息和可读 diff，便于用户继续前先审查 Agent 改了什么。

![Deepy edit diff 预览](https://raw.githubusercontent.com/kirineko/deepy/main/asset/edit-diff.webp)

### 搜索、抓取和本地命令

用 WebSearch / WebFetch 获取外部上下文，用 `@` 精确引用项目文件，用 `!` 直接执行本地命令。

![Deepy Web 检索工作流](https://raw.githubusercontent.com/kirineko/deepy/main/asset/websearch.webp)

![Deepy 本地命令模式](https://raw.githubusercontent.com/kirineko/deepy/main/asset/command_mode.webp)

## 快速开始

1. 安装 `uv`：

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. 配置 uv 镜像。

Linux / macOS: `~/.config/uv/uv.toml`

```toml
[[index]]
url = "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"
default = true
```

Windows: `%AppData%\uv\uv.toml`

```toml
[[index]]
url = "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"
default = true
```

3. 安装 Deepy：

```bash
uv tool install deepy-cli
```

安装后的命令是 `deepy`。

4. 配置 DeepSeek API Key 并启动：

```bash
deepy config setup

cd your-project
deepy
```

## 安装说明

完整安装顺序如下：

### 1. 安装 uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 配置 uv 镜像

Linux / macOS: `~/.config/uv/uv.toml`

```toml
[[index]]
url = "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"
default = true
```

Windows: `%AppData%\uv\uv.toml`

```toml
[[index]]
url = "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"
default = true
```

### 3. 安装 Deepy

```bash
uv tool install deepy-cli
```

### 4. 配置并启动

```bash
deepy config setup

cd your-project
deepy
```

升级或卸载 Deepy：

```bash
uv tool upgrade deepy-cli
uv tool uninstall deepy-cli
```

## 日常使用

交互式 Deepy 会话中的常用输入：

```text
/model       选择模型和 thinking 强度
/resume      恢复历史项目会话
/new         开始新会话
/compact     压缩当前上下文
/theme       查看或切换终端 UI 主题
@src/app.py  引用当前项目文件
!pytest -q   直接运行本地非交互命令
Esc          中断当前模型回合
Ctrl+D       连按两次退出
```

推荐工作方式：

```text
让 Deepy 排查问题、修改文件、运行测试，并总结改动。
需要精确上下文时用 @ 引用文件。
用户明确知道要执行的命令，用 ! 直接运行。
回到项目时用 /resume 恢复会话。
长会话上下文压力变高时用 /compact 生成持久摘要。
```

## 配置

Deepy 使用 TOML 配置，默认路径是 `~/.deepy/config.toml`。

```toml
[model]
api_key = "sk-..."
name = "deepseek-v4-pro"
base_url = "https://api.deepseek.com"
thinking = true
reasoning_effort = "max"

[context]
window_tokens = 1048576
compact_trigger_ratio = 0.8
reserved_context_tokens = 50000
compact_preserve_recent_messages = 2

[ui]
theme = "auto" # auto, dark, or light
```

也可以不用交互式向导，直接初始化配置：

```bash
deepy config init --api-key sk-... --model deepseek-v4-pro
deepy config theme light
```

WebSearch 默认使用 Deepy 托管的 SearXNG endpoint。你也可以改成自己的实例：

```toml
[tools.web_search]
searxng_url = "https://your-searxng.example/"
```

## 命令参考

```bash
deepy --version
deepy config setup
deepy config reset
deepy config theme
deepy doctor
deepy doctor --live --json
deepy status
deepy skills list
deepy sessions list
deepy sessions show <session-id>
deepy run "summarize this project"
```

## 项目规则和 Skills

Deepy 会自动加载项目内的规则和技能文件：

- `AGENTS.md`
- `.deepy/skills/*/SKILL.md`

这样每个仓库都可以保存自己的代码风格、验证命令、审查规则和领域工作流，而不需要修改全局配置。

## 开发

```bash
uv sync --group dev
uv run pytest
uv run ruff check
uv run pyright
uv build
```

Python 包从 `src/deepy` 构建。GitHub Pages 页面和截图资源都在包目录之外，不会进入 wheel。
