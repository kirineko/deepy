# 更新日志

[English](CHANGELOG.md)

## 0.2.34 — 2026-09-22

- 将 MiMo V2.5 / V2.5 Pro 替换为 `mimo-v2.6-flash` / `mimo-v2.6-pro`。
- 两款模型均通过 Responses 支持图片输入，覆盖粘贴图片、Read 结果、会话历史和子代理。Deepy 原生输入仍限于文本和图片，未启用音频、视频输入或媒体生成。
- 默认模型及关闭思考的输入建议模型改为 V2.6 Flash；两款模型保留 `enabled` / `disabled` 思考开关和 MiMo 工具 schema 兼容处理。
- 采用保守的 1,000,000 token 上下文窗口及文档明确的 131,072 token 输出上限，默认请求输出预算仍为 32,768 token。
- 为已移除的模型及模型限制配置提供明确替换提示，包括未激活的 provider profile；不会自动修改配置文件。

### 从 MiMo V2.5 升级

本版本从 Deepy 模型目录移除两个旧 ID。小米计划于 **2026-10-21 10:00（北京时间）**停止提供这两个模型，参见[官方模型列表](https://mimo.mi.com/docs/zh-CN/quick-start/summary/model)。

请在现有 TOML 配置的 `[providers.mimo]` 下修改 `model`：

| 旧模型 | 替换为 |
| --- | --- |
| `mimo-v2.5` | `mimo-v2.6-flash` |
| `mimo-v2.5-pro` | `mimo-v2.6-pro` |

若存在对应的 `[providers.mimo.model_limits."<model-id>"]` 表，也需更新表名中的模型 ID，或移除该覆盖项。保留密钥、URL、思考设置和有效限制值。未激活的 MiMo profile 同样需要更新。Deepy 不会静默迁移文件或改写历史会话中的模型标识。
