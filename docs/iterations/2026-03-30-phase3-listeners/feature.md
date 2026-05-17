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
| codeflicker | `.jsonl` | 逐行解析 JSON，提取 `role`（user/assistant）、`content`（字符串或 `[{type:text}]` 列表）、`timestamp`、`sessionId`、`gitBranch` |
| codeflicker | `.md` | 识别 `**User:**` / `**Assistant:**` 行（兜底） |
| Claude | `.json` | 读取 `messages[].role` + `messages[].content` |

### watch_paths 自动发现

`CLIChatWatcher` 初始化时自动扫描 `~/.codeflicker/projects/` 下的所有子目录，无需手动配置路径。每个子目录作为一个独立的 watch path，类型为 `codeflicker`。

若需自定义，可在构造时传入 `watch_paths` 参数：

```python
watcher = CLIChatWatcher(watch_paths=[
    {"type": "codeflicker", "path": "~/.codeflicker/projects/my-project"},
    {"type": "claude", "path": "~/.claude/conversations"},
])
```

### sync_all 过滤规则

`sync_all()` 扫描时自动跳过以下文件，避免处理超大文件导致性能问题：

- 最后修改时间超过 **30 天**的文件
- 文件大小超过 **1 MB** 的文件

扫描仅限目录第一层（`glob`，非 `rglob`），codeflicker 的 `.jsonl` 文件均在 project 目录直接层级。

### 写入路径（codeflicker）

codeflicker 会话按实际对话日期写入，目录结构为 **年 / 月 / 日 / 会话**：

```
{data_dir}/memory/cli_chats/codeflicker/
└── YYYY/
    └── MM/
        └── DD/
            └── {session_id}.md
```

日期取自 jsonl 中第一条消息的 `timestamp` 字段（UTC 转本地日期）；若无 `timestamp`（旧 `.md` 格式），则使用文件 mtime 日期。

**文件格式**（含 YAML frontmatter）：

```markdown
---
session_id: b957c76f
date: 2026-04-08
time_start: 2026-04-08T09:52:19.044Z
time_end: 2026-04-08T11:27:31.606Z
project: users-lianzimeng-workspace-huaqi-growing
git_branch: main
---

[2026-04-08 17:52:19] [user]: 你好
[2026-04-08 17:52:41] [assistant]: 你好！有什么可以帮你的？
```

非 codeflicker 类型仍写入 `{data_dir}/memory/cli_chats/YYYY-MM/<工具名>-<文件名>.md`（原格式不变）。

### WorkLog 自动写入

`tool_type == "codeflicker"` 时，`process_file()` 在写入 `memory/cli_chats/` 的同时，还会通过 `WorkLogWriter` 额外写入一份 WorkLog 文件：

```
{data_dir}/work_logs/YYYY-MM/YYYYMMDD_HHMMSS_{thread_id}.md
```

WorkLog 文件包含 YAML frontmatter（`date`、`time_start`、`time_end`、`thread_id`、`source`）和会话摘要正文，由 `WorkLogProvider` 在日报生成时聚合读取。

`time_start` 取自 jsonl `timestamp` 字段（精确值）；若无时间信息则使用同步时刻的 UTC 时间。非 codeflicker 类型不写入 WorkLog。

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
| `search_cli_chats_tool(query)` | 在 `memory/cli_chats/` 目录下全文搜索，支持按日期（「今天」「昨天」「4月8日」`2026-04-08`）或关键词检索，返回最多 5 条摘要 |

### 日期解析规则

`search_cli_chats_tool` 在收到 query 后，优先从中识别日期意图：

| 输入示例 | 解析结果 |
|---------|---------|
| 「今天」 / `today` | 当天日期 |
| 「昨天」 / `yesterday` | 昨天日期 |
| 「4月8日」 | 当年 04-08 |
| `2026-04-08` / `2026/04/08` | 对应日期 |
| 无日期关键词 | 全文关键词搜索，扫描最近 7 天 |

按日期检索时直接定位到 `codeflicker/YYYY/MM/DD/` 目录，返回该天全部会话摘要（包含 session_id、git_branch、用户消息预览）。

Tool 已注册进 `_TOOL_REGISTRY`，Agent 可自主决策何时调用。

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `huaqi_src/layers/data/collectors/cli_chat_parser.py` | codeflicker/Claude 对话文件解析器，包含 `CLIChatSession`、`CLIChatMessage` 数据类 |
| `huaqi_src/layers/data/collectors/cli_chat_watcher.py` | CLI 对话目录监听器，含自动发现 watch_paths 逻辑 |
| `huaqi_src/layers/data/collectors/work_log_writer.py` | WorkLog Markdown 文件写入器 |
| `huaqi_src/layers/capabilities/reports/providers/work_log.py` | WorkLogProvider，日报上下文注入 |
| `huaqi_src/cli/commands/collector.py` | `huaqi collector` 子命令（status / sync-cli） |
| `huaqi_src/agent/tools.py` | `search_cli_chats_tool`（含 `_parse_date_from_query` 日期解析） |
| `huaqi_src/layers/data/collectors/wechat_*.py` | 微信采集底层代码（已封存，无对外入口） |
| `huaqi_src/integrations/wechat_webhook.py` | 微信 Webhook 服务（已封存，无对外入口） |

---

**文档版本**: v1.5
**最后更新**: 2026-08-04
