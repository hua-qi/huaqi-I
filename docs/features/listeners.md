# 监听采集

## 概述

自动采集 CLI 工具对话历史，将数据归一化写入数据湖，并注册 Agent Tool 供 LangGraph 检索。

---

## 微信采集（已封存）

> **⚠️ 封存声明**
>
> 微信采集功能的所有对外入口（CLI 命令、Agent Tool、定时任务）已移除，底层代码文件保留但不再接入任何系统入口。
>
> **封存原因**：微信 4.x macOS 版本改用 SQLCipher 加密本地数据库，且 macOS SIP 保护阻止对 `/Applications` 目录下二进制进行重签名，无法在不破坏系统安全策略的前提下读取本地数据。
>
> **限制**：非作者本人声明，不得重新为 wechat 添加任何系统入口（CLI 命令、Agent Tool、调度任务等）。如后续微信或 Apple 提供合规接口，需作者明确声明后方可重新评估。

封存的代码文件：`wechat_reader.py`、`wechat_state.py`、`wechat_writer.py`、`wechat_watcher.py`、`wechat_webhook.py`（文件头均含封存声明注释）。

---

## CLIChatWatcher

`CLIChatWatcher` 基于 `watchdog` 文件系统监听器：检测到目标文件变化后触发回调，增量拉取新内容。

模块默认**关闭**，通过配置 `modules.cli_chat` 显式开启（Opt-in）。

### 支持格式

| 工具 | 格式 | 解析规则 |
|------|------|---------| 
| codeflicker | `.md` | 识别 `**User:**` / `**Assistant:**` 行 |
| Claude | `.json` | 读取 `messages[].role` + `messages[].content` |

### 写入路径

```
{data_dir}/memory/cli_chats/YYYY-MM/<工具名>-<原文件名>.md
```

### 配置 watch_paths

```yaml
modules:
  cli_chat: true
cli_chat:
  watch_paths:
    - type: codeflicker
      path: ~/.codeflicker/conversations
    - type: claude
      path: ~/.claude/conversations
```

### 开启方式

```bash
huaqi config set modules.cli_chat true
huaqi collector sync-cli      # 手动同步
huaqi collector status        # 查看状态
```

---

## Agent Tools

| Tool | 功能 |
|------|------|
| `search_cli_chats_tool(query)` | 在 `memory/cli_chats/` 目录下全文搜索，返回最多 3 条摘要 |

Tool 已注册进 `build_chat_graph()` 的 `tools` 列表，Agent 可自主决策何时调用。

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `huaqi_src/collectors/cli_chat_parser.py` | codeflicker/Claude 对话文件解析器 |
| `huaqi_src/collectors/cli_chat_watcher.py` | CLI 对话目录监听器 |
| `huaqi_src/cli/commands/collector.py` | `huaqi collector` 子命令（status / sync-cli） |
| `huaqi_src/agent/tools.py` | `search_cli_chats_tool` |
| `huaqi_src/collectors/wechat_*.py` | 微信采集底层代码（已封存，无对外入口） |
| `huaqi_src/integrations/wechat_webhook.py` | 微信 Webhook 服务（已封存，无对外入口） |

---

**文档版本**: v1.3
**最后更新**: 2026-03-31
