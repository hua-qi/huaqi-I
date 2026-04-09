# Codeflicker 对话记录的存储与工作日志采集

**Date:** 2026-05-04

## Context

huaqi-growing 已有一套将 codeflicker 对话提炼为成长洞察（TELOS 维度更新）的设计方案（见 2026-05-04-codeflicker-transcript-collector.md）。本文档在此基础上进一步探讨：codeflicker 对话经 huaqi 处理后，**最终以什么格式落地、存储在哪里**；以及如何将对话中的工作信息接入日报数据源，补充目前日报缺失的"今天做了什么工作"维度。

## Discussion

### 现有存储架构（三层）

| 层级 | 位置 | 格式 | 职责 |
|------|------|------|------|
| RawSignal（中转） | `signals.db` `raw_signals` 表 | SQLite | 暂存提炼后的摘要，待 DistillationPipeline 消费 |
| TELOS 维度（长期） | `~/.huaqi/data/{user}/telos/{dimension}.md` | Markdown + YAML frontmatter + Git | 存储成长认知，支持版本历史 |
| GrowthEvent（重大事件） | `signals.db` `growth_events` 表 | SQLite | 记录认知飞跃，供周报/季报消费 |

RawSignal 层存储的是 DecisionDetector 提炼后的结构化摘要，**不是原始对话**。原始 `.txt` 文件由 codeflicker 自行管理于 `~/.codeflicker/threads/{thread_id}/.meta/transcripts/`。

### 日报数据缺口

当前日报（`DailyReportAgent`）的数据提供者只有三个：DiaryProvider（手写日记）、PeopleProvider（关系人图谱）、WorldProvider（世界新闻）。**不包含任何工作内容**，导致日报无法展示"今天具体做了什么"。

codeflicker 对话天然包含工作信息，但现有 RawSignal 的 content 是 TELOS 成长视角，语义与工作日志不同，不适合直接复用。

### 方案对比

| 方案 | 描述 | 结论 |
|------|------|------|
| 每天一个 WorkLog 文件 | 当天所有会话汇总写入一个 Markdown | 结构简单，但跨天粒度不足 |
| 每会话一个 WorkLog 文件 | 每次 codeflicker 会话生成一个独立文件 | 保留时间戳和技术栈，聚合灵活，**选择此方案** |
| 复用 RawSignal | 直接从 signals.db 查询 ai_chat 数据注入日报 | 语义冲突，RawSignal 是成长视角，不适合工作日志 |

### 过滤策略决策

WorkLog 和 RawSignal 的过滤策略**分离**：
- RawSignal：经 DecisionDetector 过滤，只保留有成长价值的会话
- WorkLog：**所有会话都记录**，纯代码生成任务也是工作内容

因此 WorkLogWriter 的触发点在 DecisionDetector **之前**分叉，两条路完全独立。

## Approach

在现有 `CodeflichterWatcher` 的处理流程中，**在 DecisionDetector 之前新增一条分支**，调用 `WorkLogWriter`，将每次 codeflicker 会话的工作摘要写入独立 Markdown 文件。同时新增 `WorkLogProvider`，在日报生成时按天聚合当日所有会话记录，注入 LLM Prompt。

这样：
- 工作记录与成长提炼**完全解耦**，互不影响
- 日报获得"今天编程工作"维度
- 不修改现有 DistillationPipeline 和 TELOS 流程

## Architecture

### 完整数据流

```
codeflicker .txt（on_created，watchdog）
  ↓
CodeflichterWatcher
  ↓
TranscriptParser（解析 + 清洗）
  ↓ 分叉
  ├─→ WorkLogWriter（所有会话，不过滤）
  │     → $DATA_DIR/work_logs/YYYY-MM/YYYYMMDD_HHMMSS_{thread_id}.md
  │
  └─→ DecisionDetector（LLM 判断成长价值）
        ├─ 有价值 → RawSignal → signals.db → DistillationPipeline → TELOS 维度更新
        └─ 无价值 → 丢弃
```

### WorkLog 文件格式

**路径**：`$DATA_DIR/work_logs/YYYY-MM/YYYYMMDD_HHMMSS_{thread_id}.md`

```markdown
---
date: 2026-05-04
time_start: 2026-05-04T10:00:00Z
time_end: 2026-05-04T10:30:00Z
thread_id: gb4l7s37xp22adfrlqfz
source: codeflicker
tech_stack: [watchdog, asyncio, python]
category: problem_solving
---

设计了 transcript-collector 的文件监听方案。
选择 on_created 事件触发而非轮询，解决了 watchdog 回调与 asyncio 的线程安全冲突。
```

内容原则：工作视角（做了什么 + 结论），一段话，不超过 100 字。

### WorkLogProvider 聚合逻辑

日报触发时，`WorkLogProvider` 扫描 `work_logs/YYYY-MM/YYYY-MM-DD_*.md`，按 `time_start` 排序，生成如下格式注入日报 Prompt：

```
## 今日编程工作（来自 codeflicker）

### 10:00–10:30
设计了 transcript-collector 的文件监听方案，
选择 on_created 事件，解决了 asyncio 线程安全问题。

### 14:00–16:00
实现了 TELOS 维度更新的 5 步提炼流程，
确定了 Markdown + SQLite 双层存储架构。
```

### 最终存储全景

| 数据 | 存储位置 | 格式 | 消费方 |
|------|----------|------|--------|
| 每次工作会话 | `work_logs/YYYY-MM/YYYYMMDD_HHMMSS_{thread_id}.md` | Markdown | WorkLogProvider → 日报 |
| 成长信号（中转） | `signals.db` `raw_signals` 表 | SQLite | DistillationPipeline |
| 成长维度（长期） | `telos/{dimension}.md` | Markdown + Git | 用户查看 / 报告生成 |
| 重大成长事件 | `signals.db` `growth_events` 表 | SQLite | 周报 / 季报 |

### 新增文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `collectors/work_log_writer.py` | 新增 | 从 TranscriptParser 输出生成 WorkLog Markdown |
| `layers/capabilities/reports/providers/work_log.py` | 新增 | WorkLogProvider，按天聚合，注入日报 |
| `collectors/codeflicker_watcher.py` | 修改 | 在 DecisionDetector 前新增 WorkLogWriter 调用分支 |
