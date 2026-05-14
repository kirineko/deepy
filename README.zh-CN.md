<p align="center">
  <img src="https://raw.githubusercontent.com/kirineko/deepy/main/asset/deepy-logo.png" alt="Deepy logo" width="160">
</p>

<h1 align="center">Deepy</h1>

<p align="center">
  一个可爱的 DeepSeek 终端编程 Agent。
  <br>
  在终端里阅读项目、编辑文件、运行命令、检索资料，并持续保留项目上下文。
</p>

<p align="center">
  <a href="https://kirineko.github.io/deepy/">项目主页</a>
  ·
  <a href="README.md">English</a>
  ·
  <a href="#快速开始">快速开始</a>
</p>

![Deepy 启动画面](https://raw.githubusercontent.com/kirineko/deepy/main/asset/welcome.jpg)

## Deepy 是什么？

Deepy 是一个面向 DeepSeek OpenAI 兼容模型的 Python 终端编程 Agent。它把日常
AI 编程工作放回终端：你可以让它理解项目、阅读文件、修改代码、运行命令、搜索
资料、抓取网页，并在之后继续同一个项目会话。

Deepy 的核心目标是适配 DeepSeek V4 的 thinking 能力、长上下文、上下文缓存和终端
交互体验，让用户能清楚看到 Agent 正在做什么、用了多少 token、上下文窗口还剩多少。

## 主要特性

- DeepSeek 优先：默认使用 `deepseek-v4-pro`，启用 thinking，并设置
  `reasoning_effort=max`；也可以用 `/model` 在 V4 Pro / V4 Flash 之间切换，
  并选择 `none`、`high`、`max` 三档 thinking 强度。
- 基于 OpenAI Agents SDK，通过 `OpenAIChatCompletionsModel` 调用 DeepSeek。
- 面向项目的编程工具：读取文件、修改文件、运行 shell 命令、展示可读 diff。
- 内置资料查阅能力：支持 WebSearch，也支持给定完整 URL 后直接 WebFetch。
- 支持 session 历史、`/resume`、`/new`、上下文状态显示和自动 compact。
- 只使用 TOML 配置，默认保存到 `~/.deepy/config.toml`。
- 适配主题的 Rich 终端 UI：Markdown 渲染、thinking 展示、每轮 usage、上下文窗口状态、版本更新检测。

## 效果预览

### 项目启动

Deepy 启动后会展示当前模型、thinking 设置、工作目录和核心命令。

![Deepy 启动画面](https://raw.githubusercontent.com/kirineko/deepy/main/asset/welcome.jpg)

### 软件开发能力

让 Deepy 编写代码、补充测试、运行验证命令，并总结结果。

![Deepy 编码与 diff 展示](https://raw.githubusercontent.com/kirineko/deepy/main/asset/coding-1.jpg)

Deepy 也可以把命令输出整理成更适合阅读的项目说明、代码片段和测试覆盖结果。

![Deepy 项目总结](https://raw.githubusercontent.com/kirineko/deepy/main/asset/coding-2.jpg)

### 资料查阅能力

Deepy 提供 WebSearch 和 WebFetch 工具，既可以搜索最新资料，也可以根据完整 URL
抓取指定页面内容。

![Deepy Web 检索与抓取](https://raw.githubusercontent.com/kirineko/deepy/main/asset/websearch.jpg)

## 快速开始

首个 PyPI 版本发布后，可以直接安装：

```bash
uv tool install deepy-cli
```

安装后的命令仍然是 `deepy`。

也可以安装 GitHub 上的最新代码：

```bash
uv tool install git+https://github.com/kirineko/deepy.git
```

配置 DeepSeek API Key：

```bash
deepy config setup
```

在项目目录里启动：

```bash
cd your-project
deepy
```

## 配置

Deepy 只支持 TOML 配置，不支持 JSON 配置。

```toml
# ~/.deepy/config.toml
[model]
api_key = "sk-..."
name = "deepseek-v4-pro"
base_url = "https://api.deepseek.com"
thinking = true
reasoning_effort = "max" # thinking 开启时可选 high 或 max

[context]
window_tokens = 1048576
compact_trigger_ratio = 0.8
reserved_context_tokens = 50000
compact_preserve_recent_messages = 2

[ui]
theme = "auto" # auto, dark, light
```

交互式 `/model` 当前支持 `deepseek-v4-pro` 和 `deepseek-v4-flash`。thinking
强度选择 `none` 会保存为 `thinking = false`；选择 `high` 或 `max` 会保存为
`thinking = true`，并写入对应的 `reasoning_effort`。

WebSearch 默认使用 Deepy 托管的 SearXNG 搜索服务。你也可以改成自己的
SearXNG 实例：

```toml
[tools.web_search]
searxng_url = "https://your-searxng.example/"
```

也可以通过命令行初始化：

```bash
deepy config init --api-key sk-... --model deepseek-v4-pro
```

如果你的终端是浅色背景，Deepy 的部分文字对比度不够，可以显式切换 UI 主题：

```bash
deepy config theme light
```

## 常用命令

```bash
deepy --version
deepy config setup
deepy config reset
deepy config theme
deepy config theme light
deepy doctor
deepy doctor --live --json
deepy status
deepy skills list
deepy sessions list
deepy sessions show <session-id>
deepy run "summarize this project"
```

交互模式里的核心命令：

```text
/skills   查看可用 skills
/model    选择模型和 thinking 强度
/new      开始新会话
/resume   选择历史会话继续
/compact  压缩当前会话上下文
/theme    查看或切换 UI 主题
/reset    删除配置并重新引导 setup
/         打开命令菜单
Esc       中断当前模型回合
Ctrl+D    连按两次退出
```

## 项目规则和 Skills

Deepy 会自动加载项目内的规则和技能文件：

- `AGENTS.md`
- `.deepy/skills/*/SKILL.md`

这样每个项目都可以定义自己的代码风格、验证命令、审查规则和领域技能。

## 开发

```bash
uv sync --group dev
uv run pytest
uv run ruff check
uv run pyright
uv build
```

Python 包从 `src/deepy` 构建。GitHub Pages 页面和截图资源都在包目录之外，不会进入
wheel。

## 发布状态

Deepy `0.1.9` 通过 GitHub 和 PyPI 发布。独立可执行文件和 npm wrapper 可以后续再加，
当前主要发行形态是 Python CLI。
