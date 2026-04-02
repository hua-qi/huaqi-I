# 实现细节设计文档

> 本文档是「个人成长系统完整设计文档」的实现细节补充，覆盖数据库 Schema、文件格式、Prompt 设计和冷启动流程。

---

## 一、RAW_SIGNAL 数据库 Schema

### 主表

```sql
CREATE TABLE raw_signals (
    id            TEXT PRIMARY KEY,      -- UUID
    user_id       TEXT NOT NULL,         -- 多用户隔离
    source_type   TEXT NOT NULL,         -- journal/ai_chat/wechat/reading/audio/video/image/calendar/absence/...
    timestamp     TEXT NOT NULL,         -- ISO 8601，事件发生时间
    ingested_at   TEXT NOT NULL,         -- 写入系统的时间
    content       TEXT NOT NULL,         -- 转换后的文本内容
    metadata      TEXT,                  -- JSON，来源特定字段
    raw_file_ref  TEXT,                  -- 原始文件路径（音视频/图片）
    processed     INTEGER DEFAULT 0,     -- 0=待处理 1=已提炼
    distilled     INTEGER DEFAULT 0,     -- 0=热记忆 1=已蒸馏归档
    created_at    TEXT NOT NULL
);
```

### 索引

```sql
CREATE INDEX idx_user_timestamp ON raw_signals(user_id, timestamp DESC);
CREATE INDEX idx_user_processed  ON raw_signals(user_id, processed);
CREATE INDEX idx_user_source     ON raw_signals(user_id, source_type);
CREATE INDEX idx_user_distilled  ON raw_signals(user_id, distilled);
```

### metadata JSON 结构（按 source_type）

```json
// journal
{ "mood": "平静", "tags": ["工作", "反思"] }

// wechat
{ "participants": ["张三", "李四"], "chat_name": "家庭群" }

// reading
{ "book_title": "穷查理宝典", "author": "查理·芒格", "highlight": true }

// audio
{ "duration_seconds": 183, "speaker_count": 1 }

// absence（沉默期，系统自动生成）
{ "days": 30, "last_signal_id": "uuid-xxx" }
```

---

## 二、TELOS Markdown 文件格式

### 目录结构

```
~/.huaqi/telos/
├── INDEX.md              ← 所有维度的索引入口
├── beliefs.md
├── models.md
├── narratives.md
├── goals.md
├── challenges.md
├── strategies.md
├── learned.md
├── people.md
├── shadows.md
├── meta.md               ← META 特殊维度
└── _archive/             ← 归档的旧维度（不删除）
    └── learning_languages.md
```

### 单个维度文件格式

```markdown
---
dimension: beliefs
layer: core
confidence: 0.82
updated_at: 2026-01-04
update_count: 7
---

## 当前认知

选择比努力更重要。在正确的方向上努力，才有复利效应。
在错误的赛道上，努力只是加速消耗。

深度优于广度。宁愿在少数事情上做到极致，
也不愿在很多事情上浅尝辄止。

---

## 更新历史

### v7 · 2026-01-04
**变化**：从「努力一定有回报」修正为「选择比努力更重要」
**触发**：日记连续 4 次提到「方向感」，1 次明确写到「努力错了方向很可怕」
**置信度**：0.82

### v6 · 2025-11-12
**变化**：新增「深度优于广度」信念
**触发**：读完《深度工作》后的读书笔记，结合 3 条日记信号
**置信度**：0.75
```

### INDEX.md 格式

```markdown
# TELOS 索引

> 最后更新：2026-01-04 · 共 9 个活跃维度

## 核心层（变化最慢）
- [beliefs.md](beliefs.md) — 选择比努力重要；深度优于广度（v7，置信度 0.82）
- [models.md](models.md) — 系统思维；第一性原理（v4，置信度 0.71）
- [narratives.md](narratives.md) — 自我描述为「慢热但持久的人」（v3，置信度 0.65）

## 中间层（定期变化）
- [goals.md](goals.md) — 近期：完成 huaqi 系统 MVP（v12，置信度 0.90）
- [challenges.md](challenges.md) — 当前卡点：执行力和专注度（v8，置信度 0.88）
- [strategies.md](strategies.md) — 倾向先想清楚再动手（v5，置信度 0.70）

## 表面层（频繁变化）
- [learned.md](learned.md) — 最近：LangGraph 状态机设计（v31，置信度 0.95）
- [people.md](people.md) — 记录 12 个重要关系（v19，置信度 0.90）
- [shadows.md](shadows.md) — 容易高估自己的执行速度（v6，置信度 0.60）

## 特殊
- [meta.md](meta.md) — 提炼偏好校正记录（v14）
```

### META 维度格式

```markdown
---
dimension: meta
updated_at: 2026-01-04
---

## 提炼偏好

### 用户反馈记录

| 日期 | Agent 提炼结论 | 用户反馈 | 校正方向 |
|---|---|---|---|
| 2026-01-02 | 你似乎对社交感到焦虑 | 不对，我只是内向 | 区分「内向」和「焦虑」|
| 2025-12-20 | 你最近压力很大 | 对，准确 | 强化情绪类信号识别 |

## 活跃维度列表

当前活跃维度：beliefs / models / narratives / goals /
challenges / strategies / learned / people / shadows

## 维度演化历史

| 维度 | 操作 | 日期 | 原因 |
|---|---|---|---|
| health | 用户创建 | 2025-10-15 | 开始关注身体状态 |
| learning_languages | 归档 | 2025-12-01 | 6个月无信号更新 |
```

---

## 三、信号提炼管道 Prompt 设计

### 总体上下文（每步都携带）

```
每次调用 AI 提炼时，固定传入：
1. 当前 TELOS INDEX.md 内容（让 AI 基于「已知的你」判断）
2. META 中的活跃维度列表（兼容动态维度）
3. 待处理的 RAW_SIGNAL 内容
```

### Step 1：单条信号分析

**触发**：每条新 RAW_SIGNAL 写入后

```
System:
你是用户的个人成长分析师。
你的任务是分析用户的输入信号，判断它对用户的自我认知有什么影响。

以下是你目前对这个用户的了解（TELOS 快照）：
{telos_index}

以下是该用户当前所有活跃的 TELOS 维度：
{active_dimensions}
（标准维度：beliefs/models/narratives/goals/challenges/strategies/learned/people/shadows）
（用户自定义维度：{custom_dimensions}）

User:
分析以下输入信号：

来源：{source_type}
时间：{timestamp}
内容：{content}

请从以上活跃维度中判断本条信号涉及哪些维度。
如果信号内容不属于任何现有维度，请在 new_dimension_hint 字段说明。

输出 JSON：
{
  "dimensions": ["beliefs", "challenges"],
  "emotion": "negative",
  "intensity": 0.7,
  "signal_strength": "strong",
  "strong_reason": "用户明确表达了立场",
  "summary": "用户对方向感感到迷茫",
  "new_dimension_hint": null
}
```

### Step 2：跨时间聚合（纯数据库查询，无 Prompt）

```sql
SELECT * FROM raw_signals
WHERE user_id = ?
  AND processed = 0
  AND timestamp >= ?     -- 最近 30 天
ORDER BY timestamp DESC
```

按维度分组，统计：
- 同维度信号数量
- 情感方向是否一致
- 最近一次 vs 最早一次的变化趋势

### Step 3：更新决策

**触发**：同一维度信号数量超过阈值时

```
System:
你是用户的个人成长分析师。
你的任务是判断积累的信号是否说明用户的某个认知发生了变化。

以下是你目前对这个用户的了解：
{telos_index}

User:
以下是最近 {days} 天，关于「{dimension}」维度的 {count} 条信号摘要：

{signal_summaries}

当前该维度的认知是：
{current_dimension_content}

请判断：
1. 这些信号是在「强化」当前认知，还是在「挑战」它？
2. 是否需要更新该维度？

输出 JSON：
{
  "should_update": true,
  "update_type": "challenge",
  "confidence": 0.75,
  "reason": "用户连续 4 次提到方向感问题，且明确质疑了「努力一定有回报」",
  "suggested_content": "选择比努力更重要..."
}
```

### Step 4：生成 TELOS 更新内容

**触发**：Step 3 的 should_update = true

```
System:
你是用户的个人成长分析师。
你的任务是用自然、简洁的语言描述用户认知的变化。
写给用户自己看，不要用分析腔，要像朋友在帮他整理想法。

User:
维度：{dimension}
旧版本内容：{old_content}
触发这次更新的信号摘要：{signal_summaries}
更新建议：{suggested_content}

请生成：
1. 新版本的认知描述（简洁，100字以内）
2. 更新历史条目

输出 JSON：
{
  "new_content": "选择比努力更重要...",
  "history_entry": {
    "change": "从「努力一定有回报」修正为「选择比努力更重要」",
    "trigger": "日记连续 4 次提到「方向感」，1 次明确写到「努力错了方向很可怕」"
  }
}
```

### Step 5：成长事件判断

**触发**：Step 4 完成后

```
System:
你是用户的个人成长见证者。
你的任务是识别用户真正有意义的内在变化，用温暖的语言记录下来。
不是所有更新都值得成为成长事件，只有跳跃性的认知变化才值得。

判断标准：
- 核心层维度变化 → 几乎总是值得
- 中间层维度的方向性转变 → 值得
- 表面层的日常积累 → 通常不值得

User:
维度：{dimension}（{layer}层）
变化前：{old_content}
变化后：{new_content}
更新原因：{trigger}

输出 JSON：
{
  "is_growth_event": true,
  "narrative": "你开始相信选择比努力更重要了。这个转变不是一夜之间发生的——过去一个月，你在日记里反复探索这个问题，最终想清楚了。",
  "title": "开始相信选择的力量"
}
```

### 动态维度兼容机制

```
Step 1 输出 new_dimension_hint 不为 null
    ↓
累积同类 hint 达到阈值（≥5 条，跨越≥7 天）
    ↓
Agent 向用户提案：
「我注意到你频繁记录 [主题] 相关内容，
  建议新增 [维度名] 维度，是否创建？」
    ↓
用户确认 → META 更新活跃维度列表
用户拒绝 → 记录到 META，降低该类 hint 的权重
```

### 五步全景

```
RAW_SIGNAL 进入
    ↓
Step 1  单条分析（注入活跃维度列表）        每条都跑
        → 命中现有维度  → 走正常流程
        → 发现未知内容  → new_dimension_hint 累积
    ↓
Step 2  跨时间聚合（纯数据库查询）          无 Prompt
    ↓
Step 3  更新决策                           按维度跑
    ↓  should_update = false → 归档，结束
Step 4  生成更新内容                       有更新才跑
    ↓
Step 5  成长事件判断                       有更新才跑

大多数信号在 Step 3 结束，控制 AI 调用成本。
```

---

## 四、冷启动引导问卷

### 设计原则

```
问题少而精    10 个以内，覆盖最重要的维度
问题要开放    不要选择题，让用户自由表达
顺序要自然    像朋友聊天，不像填表格
允许跳过      用户可以跳过任何问题，后面补
置信度诚实    初始 TELOS 标记为「来自自述，待观察验证」（confidence: 0.5）
```

### 10 个核心问题

```
Q1（GOALS · 表面层，热身）
「你现在最想做成的一件事是什么？
  可以是工作上的，也可以是生活里的。」

Q2（CHALLENGES · 中间层）
「什么事情最近让你感到卡住或者消耗？」

Q3（LEARNED · 表面层）
「最近有没有什么让你觉得「哦，原来如此」的认知？
  可以是读到的、聊到的、经历到的。」

Q4（NARRATIVES · 核心层）
「你会怎么向一个刚认识的朋友介绍自己？」

Q5（BELIEFS · 核心层）
「你最看重什么？有没有什么原则是你不愿意妥协的？」

Q6（MODELS · 核心层）
「你觉得这个世界是怎么运转的？
  有没有某个框架或者比喻，是你经常用来理解事情的？」

Q7（STRATEGIES · 中间层）
「你面对一个新的困难或挑战时，通常怎么处理？」

Q8（PEOPLE · 表面层）
「你生命里现在最重要的几个人是谁？
  他们对你意味着什么？」

Q9（SHADOWS · 表面层，最后问，因为最敏感）
「如果你最了解你的朋友来评价你，
  他会说你最大的盲点或弱点是什么？」

Q10（META · 特殊，关于系统本身）
「你希望我在了解你的过程中，特别注意什么？
  有没有什么是你不想让我记录的？」
```

### 对话流程

对话式逐步推进，Agent 每次提问前先回应上一个答案：

```
Agent：
「你好，我是你的成长伙伴。在我们正式开始之前，
  我想先了解一下你。不用担心说错，
  说什么都好，我只是想认识你。

  先问你一个简单的问题——
  你现在最想做成的一件事是什么？」

用户回答后 →

Agent：
「明白了。[简短回应用户的答案]

  那最近有没有什么事情让你感到卡住？」

...以此类推，直到 10 个问题问完或用户主动结束
```

### 问卷结束后的处理

**第一步：生成初始 TELOS**

```
System:
根据用户的自述，生成初始 TELOS 各维度内容。
置信度统一标记为 0.5（来自自述，待后续观察验证）。
没有回答的维度输出 null，跳过不生成。
语言风格：简洁、不要分析腔。

User:
以下是用户对问卷的回答：
{qa_pairs}

请为每个有答案的维度生成初始内容。
```

**第二步：用户确认总结**

```
Agent：
「我整理了一下你说的，看看我理解得对不对：

  你现在最想做的是 [GOALS]
  你觉得自己最看重 [BELIEFS]
  你面对挑战时倾向于 [STRATEGIES]

  有没有哪里理解偏了？」
```

用户纠正的内容直接写入 META，作为第一批校正记录。

**第三步：说明学习方式 + 引导历史数据导入**

```
Agent：
「好的，我对你已经有了一个初步的了解，
  但现在的认识还很浅——置信度大概只有 50%。

  随着你写日记、和我聊天、导入你的阅读记录，
  我会越来越了解你。

  有什么想导入的历史数据吗？
  比如以前的日记、读书笔记、聊天记录。」
```

### 冷启动完整流程

```
启动系统
    ↓
10 个问题对话式问卷（可随时跳过）
    ↓
生成初始 TELOS（confidence: 0.5，标注「来自自述」）
    ↓
用户确认/纠正总结（纠正内容写入 META 第一批校正）
    ↓
提示导入历史数据（可选）
    ↓
正式进入系统
```

---

**文档版本**：v1.0
**创建时间**：2026-01-04
**对应文档**：个人成长系统完整设计文档 v1.0
