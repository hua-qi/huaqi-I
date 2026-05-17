# Codeflicker 对话记录采集与成长洞察

**Date:** 2026-05-04

## Context

huaqi-growing 目前的数据源主要来自用户与 huaqi 本身的对话、日记和世界新闻。用户每天也在大量使用 codeflicker 等 AI 编程助手工具，这些对话中包含丰富的技术决策、问题解法和技能习得信息，却没有被纳入 huaqi 的成长追踪体系。

目标是将 codeflicker 的对话记录作为新数据源接入 huaqi，让 TELOS 引擎能从编程工作中自动提炼成长洞察，更新技能维度（Technique）、问题解决（Observation）等成长指标。

## Discussion

**采集目的**：最终确认为「成长洞察」，而非记忆扩充——即从编程对话中提炼技术决策和技能成长，写入 TELOS，而不是让 huaqi 对话时能引用 codeflicker 历史。

**采集时机**：实时监听文件变化，会话结束后立即处理，无需手动触发。

**采集内容**：只提取结论和决策（技术选型、架构决定、问题解法），过滤过程性内容和纯代码生成任务。

**三种方案对比**：

| 方案 | 描述 | 复杂度 |
|------|------|--------|
| A：规则过滤 | 关键词匹配提取决策段落 | 低，但质量有限 |
| B：LLM 提炼 | 整个对话一次性 LLM 摘要 | 中，质量高 |
| C：增量处理 | 增量监听 + 分段判断 + 会话结束汇总 | 高，最精细 |

最终选择**方案 C**，但在确认 codeflicker 文件写入机制后，方案 C 的复杂度大幅简化。

**关键事实确认**：
- codeflicker transcript 文件路径：`~/.codeflicker/threads/{thread_id}/.meta/transcripts/{timestamp}-{summary}.txt`
- 每个 `.txt` 文件 = 一次完整会话，**会话结束后一次性写入**，不持续追加（Header 中有完整 Time Range 起止时间为证）
- 因此不需要字节偏移追踪，也不需要超时检测，监听 `on_created` 即可

**文件格式复杂度**：user 输入包含大量 `<file_selection>`、`<context_section>` 等 XML 标签和代码片段，需要清洗；assistant 段有多个（thinking、tool call、最终回复），只取最后纯文本段。

**噪音过滤**：大量 transcript 是纯代码生成任务，成长价值低，需要 LLM 先判断是否值得处理再决定是否提炼。

**监听方式**：集成进现有 `huaqi daemon`，watchdog Observer 作为守护线程挂载，无需单独守护进程。

## Approach

将 codeflicker watcher 集成进现有 daemon 启动流程：

1. `huaqi daemon start` 时，同步启动 `CodeflichterWatcher`（watchdog Observer 守护线程）
2. 监听 `~/.codeflicker/threads/*/. meta/transcripts/` 下新 `.txt` 文件出现（`on_created`）
3. 新文件 = 一次完整会话 → 解析 + 清洗 → LLM 判断价值 → 有价值则提炼 → `RawSignal` → 现有 `DistillationPipeline` → TELOS 更新
4. 已处理文件记录在 `processed_files.json`，防止重启后重复处理

## Architecture

### 总体数据流

```
~/.codeflicker/threads/*/. meta/transcripts/*.txt（新文件出现）
  ↓ on_created（watchdog）
CodeflichterWatcher
  ↓
TranscriptParser（解析 + 清洗）
  ├─ 提取 header：Thread ID / Time Range / Agent Mode
  ├─ 提取 user query：剥离 XML 标签，只保留自然语言
  └─ 提取 assistant 最终回复：取最后一个纯文本 assistant: 段
  ↓
DecisionDetector（LLM 轻量判断）
  ├─ 有价值（技术决策/架构思考/问题解法）→ 提炼结构化摘要
  └─ 无价值（纯代码生成/格式转换）→ 丢弃
  ↓
RawSignal(source_type=AI_CHAT, metadata={tool_type: "codeflicker", ...})
  ↓
现有 DistillationPipeline（不改动）→ TelosEngine → TELOS 成长维度更新
```

### 新增 / 修改文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `collectors/codeflicker_watcher.py` | 新增 | watchdog 监听 + 已处理记录（processed_files.json） |
| `collectors/transcript_parser.py` | 新增 | 解析并清洗 codeflicker txt 文件 |
| `collectors/decision_detector.py` | 新增 | LLM 判断是否有成长价值 + 提炼摘要 |
| `raw_signal/converters/cli_chat.py` | 新增 | 清洗后内容 → RawSignal 转换器 |
| `scheduler/manager.py` 或 `jobs.py` | 微调 | daemon start 时启动 CodeflichterWatcher |
| `cli/commands/collector.py` | 微调 | 添加 `codeflicker watch` 子命令（手动启动） |
| `config.yaml` | 扩展 | 新增 `cli_watchers.codeflicker.enabled / path` 配置项 |

### DecisionDetector Prompt 设计

```
以下是用户与 AI 编程助手的一段对话：
{cleaned_content}

判断这段对话是否包含以下任意一种内容：
1. 技术决策（选了哪个方案/库/架构）
2. 问题解决（遇到什么 bug，怎么解决的）
3. 新技能习得（学到了什么概念或技术）

如果有，提取：
- decision: 结论的一句话总结
- tech_stack: 涉及的技术列表
- category: skill | problem_solving | architecture

如果没有，返回 null。
```

### RawSignal 示例

```python
RawSignal(
    source_type=SourceType.AI_CHAT,
    content="""
    [会话总结] 2026-05-04 codeflicker
    技术决策：决定用 watchdog on_created 监听 transcript 文件，而非轮询
    问题解法：解决了 watchdog 回调与 asyncio 的线程安全问题
    """,
    metadata={
        "tool_type": "codeflicker",
        "thread_id": "gb4l7s37xp22adfrlqfz",
        "session_file": "20260504-xxxx.txt",
        "time_range_start": "2026-05-04T10:00:00Z",
        "time_range_end": "2026-05-04T10:30:00Z",
        "tech_stack": ["watchdog", "asyncio"],
        "category": "problem_solving",
    }
)
```

### TELOS 维度映射

| 对话内容 | TELOS 维度 |
|---------|-----------|
| 学了新技术/库 | T (Technique) |
| 解决了难题 | T + O (Observation) |
| 架构决策 | T + S (Self，反映思维模式) |
| 有挫败感或成就感 | E (Emotion) |

### Daemon 集成方式

```
huaqi daemon start
  ↓
register_default_jobs()        ← 现有
scheduler.start()              ← 现有
codeflicker_watcher.start()    ← 新增（watchdog Observer，守护线程）
```

stop 时同步调用 `codeflicker_watcher.stop()`，优雅关闭 Observer。
