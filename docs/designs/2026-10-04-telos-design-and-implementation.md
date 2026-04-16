# Telos 设计与实现

**Date:** 2026-10-04

## Context

Telos 是 huaqi 的核心成长认知系统，参考 Daniel Miessler 的 [Personal AI Infrastructure](https://danielmiessler.com/p/personal-ai-infrastructure/) 设计，目标是**捕捉用户的心智模型**，让 AI 对用户有深层、动态的理解，从而给出更有针对性的回复和建议。

核心主张：AI 对用户的帮助质量，完全取决于它对用户的上下文理解深度。Telos 在"向量记忆"之上多做了一层——将历史信号蒸馏为具名的认知维度，实现压缩、稳定性和可解释性。

原始实现存在几个关键问题：
- Agent 对话时未注入 Telos 数据（`TelosContextBuilder` 写好了但未接入）
- RawSignal 无自动提炼触发，信号永远躺在数据库
- 所有集成测试均使用 MagicMock，未经真实 LLM 验证
- `people` 维度与其他8个维度性质完全不同，强行放在同一框架内

本文档记录对上述问题的系统性重新设计。

---

## Discussion

### 1. 维度抽象的价值

相比直接向量化所有历史信号，Telos 多做了一层蒸馏抽象，价值体现在三点：
- **压缩**：8个维度摘要远比几百条原始信号更容易塞进 context window
- **稳定性**：维度内容是提炼后的认知，比原始信号更精炼、噪声更低
- **可解释性**：AI 基于"你的 beliefs 维度显示..."给出建议，比"你之前提过..."更有深度

代价是提炼准确性完全依赖 LLM，存在将一时情绪误判为稳定信念的风险。

### 2. 维度时效问题

`confidence`（置信度）只解决"我有多确定这个维度是对的"，但不解决"这条内容是否已经过时"。用户状态变化后，旧维度内容可能持续以高置信度注入每次对话。

三种应对方案对比：
- **方案A**：置信度时间衰减（简单但内容还在，AI 依然读到）
- **方案B**：引入 `activity_score`（增加新概念，复杂度上升）
- **方案C**：定时信号复审（LLM 主动判断维度是否还准确）

**结论：选方案C**。与现有5步提炼逻辑天然一致，无需引入新概念。实现为：定时检查超过 N 天无信号的维度，触发轻量复审流程（相当于无新信号触发的 Step3）。

### 3. People 维度的失误

`people` 与其他8个维度在本质上不同：
- 存储的是关系数据（多个 Person 对象），而非用户认知（一段文字）
- 更新语义是"新增/更新人物"，而非"内容替换"
- 信号密度极低（可能一周才一条），和 `learned` 等高频维度用同样的 `signal_threshold=3` 不合理
- 现有代码中 `PeoplePipeline` 完全未接入提炼流水线，实为空壳

**结论**：`people` 从8个维度中移除，作为 Telos 下的独立子系统，有专属处理管道。

### 4. 5步流水线效率

原始设计最坏情况：1条信号涉及3个维度 → Step1(1次) + 每个维度 Step3/4/5(各1次) = **10次串行 LLM 调用**。

两个优化方向：
- **合并 Step3/4/5**：三步的"判断→生成→评估"是同一认知过程，可合并为1次 LLM 调用，输出结构化 JSON
- **多维度并行**：Step1 完成后，多个维度的处理并行执行

**结论：两个优化同时做**。最坏情况从10次串行 → 实际约2次 LLM 时间（Step1 串行 + 其余并行）。

### 5. 置信度机制

原始实现问题：
- LLM 在 Step3 直接输出 confidence 数字，无依据，大概率是"感觉差不多"的值
- 用户纠错固定减 0.15，不区分纠错力度

**结论**：置信度由两个有明确来源的分量计算：
```
confidence = count_score * 0.4 + consistency_score * 0.6
```
- `count_score`：近30天涉及该维度的信号数 / 10（纯 DB 统计，无需 LLM）
- `consistency_score`：LLM 在合并后的 Step3+4+5 中判断信号方向一致性（0.0~1.0）

用户纠错时，不固定减值，而是由 LLM 判断纠错力度，调整 `consistency_score`（-0.3 轻微纠错 / -0.6 完全否定），再重新计算 confidence。

### 6. Agent 上下文注入

原始问题：`TelosContextBuilder` 已实现但未接入 `chat_nodes.py`，Agent 对话时 System Prompt 里只有 UserProfile，完全看不到 Telos 数据。

注入方式讨论：
- INDEX.md 全量注入：内容只有每个维度前30字，共20行左右，token 压力小，但摘要过于简短
- 各维度完整文件注入：包含 frontmatter + 当前认知 + 更新历史，历史部分随时间增长

**结论**：各维度读取 `frontmatter + ## 当前认知`，跳过 `## 更新历史`。每个维度约5~10行，8个维度共50~80行，内容完整且长度可控。不使用 INDEX.md。

历史记忆检索方式：不预载入 `relevant_history`，改为给 AI 提供 `search_memory` tool，由 AI 根据对话内容自主决定是否检索，避免每次都注入可能无关的片段。

### 7. 冷启动

新用户首次使用时8个维度全空，AI 对用户一无所知。

**结论**：5个问题的问卷，每个问题覆盖1-2个维度，设计为高密度自然问题而非结构化填表。用户回答后 LLM 一次调用批量提取所有维度内容，**直接写入**（跳过提炼管道），初始置信度统一设为 0.4（标记为"问卷初始化，待验证"）。

---

## Approach

### 核心方向

1. **People 独立**：从维度列表移除，建立专属管道，在 Step1 分叉后并行处理
2. **流水线合并+并行**：Step3/4/5 合并为一次 LLM 调用，多维度并行执行
3. **置信度重构**：改为 `count_score * 0.4 + consistency_score * 0.6`，有明确来源
4. **Agent 注入接入**：在 `build_context` 节点读取各维度文件（跳过历史），组装 System Prompt
5. **定时复审**：定期检查长期无信号的维度，触发轻量 LLM 复审
6. **冷启动问卷**：5个问题 → 1次 LLM 提取 → 直接写入，初始置信度 0.4

---

## Architecture

### 维度定义

移除 `people` 后，标准维度为8个：

| 层级 | 维度 | 说明 |
|------|------|------|
| core | beliefs | 信念和价值观 |
| core | models | 世界观和心智模型 |
| core | narratives | 关于自己的叙事和自我认知 |
| middle | goals | 短/中/长期目标 |
| middle | challenges | 正在面对的困难和卡点 |
| middle | strategies | 应对问题的方式和习惯 |
| surface | learned | 学到的知识和洞察 |
| surface | shadows | 阴影自我与未表达的部分 |

`people` 作为 Telos 下的独立子系统，不参与维度流水线。

### 优化后的提炼流水线

```
DistillationPipeline.process(signal)
  ↓
Step1：分析信号（1次 LLM）
  输出：
    - dimensions: ["goals", "challenges"]   # 涉及的维度
    - has_people: True
    - mentioned_names: ["张伟", "老李"]
  ↓
并行分叉：
  ├── [goals]     Step3+4+5 合并（1次 LLM）
  ├── [challenges] Step3+4+5 合并（1次 LLM）
  └── [People]    PeoplePipeline（1次 LLM）
```

**合并后 Step3+4+5 的 prompt 输出结构：**

```json
{
  "should_update": true,
  "new_content": "...",
  "consistency_score": 0.8,
  "is_growth_event": true,
  "growth_title": "...",
  "growth_narrative": "..."
}
```

**置信度计算：**

```python
recent_count = query_signal_count(dimension, days=30)
count_score = min(recent_count / 10, 1.0)
confidence = count_score * 0.4 + consistency_score * 0.6
```

**定时复审（新增）：**

定时任务检查各维度的 `last_signal_at`，超过 N 天无信号的维度进入轻量复审：
```
复审流程：
  读取当前维度内容
  ↓
  LLM 判断："根据该维度最近的信号缺失，内容是否可能已过时？"
  ↓
  如过时：降低 consistency_score，重新计算 confidence
  如仍有效：维持不变，更新 last_reviewed_at
```

### PeoplePipeline

```
PeoplePipeline.process(signal, mentioned_names)
  ↓
People-Step1：提取人物信息（1次 LLM）
  对每个人名，提取：
    - 情感倾向（-1.0 ~ 1.0）
    - 互动类型（合作/冲突/日常/初识/久未联系）
    - 新属性（职位变化、新标签等）
    - 关系变化描述
  ↓
People-Step2：写入 PeopleGraph（纯 merge 逻辑，无 LLM）
  - 已有人物 → 追加 InteractionLog + 更新 EmotionalTimeline
  - 新人物 → 创建 Person，打初始标签
```

**Person 模型扩展（新增字段）：**

```python
@dataclass
class InteractionLog:
    date: str
    signal_id: str           # 关联原始信号
    interaction_type: str    # 合作/冲突/日常/初识/久未联系
    summary: str             # 一句话摘要

@dataclass
class EmotionalTimeline:
    date: str
    score: float             # -1.0 ~ 1.0
    trigger: str             # 触发原因

@dataclass
class Person:
    # 现有字段...
    interaction_logs: List[InteractionLog] = field(default_factory=list)   # 新增
    emotional_timeline: List[EmotionalTimeline] = field(default_factory=list)  # 新增
```

### Agent 上下文注入

**build_context 节点流程：**

```
build_context(state)
  ├── UserProfile.get_summary()
  │     → "用户叫张三，是一名独立开发者，住在上海"
  │
  ├── TelosManager.list_active() × 8个维度
  │     → 各读取 frontmatter + ## 当前认知（跳过更新历史）
  │     → 每个维度约5~10行，共50~80行
  │
  └── PeopleGraph.get_top_n(n=5, strategy="freq+emotion")
        → 按互动频率 + 情感强度取 Top N
        → 每人一行摘要
```

**System Prompt 结构：**

```
# 你是 Huaqi...（人格设定）

## 你对这个用户的了解

### 身份
用户叫张三，是一名独立开发者，住在上海。

### 核心认知（TELOS）

**beliefs**（置信度 0.8）
选择比努力重要，专注在少数关键事情上...

**goals**（置信度 0.75）
完成 huaqi MVP，今年内找到第一个付费用户...

...（8个维度）

### 核心关系人
- 老李（mentor）：近期有一次冲突，情感 -0.2，需要关注
- 小王（合伙人）：合作顺畅，情感 +0.7
```

**可用工具：**

```
search_memory(query)   → 检索相关历史片段（向量检索）
search_person(name)    → 获取某人完整画像 + 情感时序
```

历史记忆不预载入 prompt，由 AI 根据对话内容主动调用 `search_memory`。

### 冷启动问卷

**5个问题设计：**

| 问题 | 初始化维度 |
|------|-----------|
| 你现在最想做成的一件事是什么？是什么在阻止你？ | goals + challenges |
| 你觉得一个人要做成事，最关键的是什么？ | beliefs + models |
| 你怎么描述自己？有没有一面是你不太愿意承认但确实存在的？ | narratives + shadows |
| 你现在用什么方式推进事情？最近学到了什么让你觉得有用？ | strategies + learned |
| 你生活里现在最重要的1-2个人是谁？你们的关系是什么状态？ | people |

**初始化流程：**

```
展示5个问题
  ↓
用户回答完成
  ↓
LLM 一次调用，输入5个回答，输出8个维度内容 + Top N 人物
  ↓
TelosManager 直接写入（跳过提炼管道）
PeopleGraph 直接写入核心人物
  ↓
所有维度 confidence = 0.4（标记为"问卷初始化，待验证"）
  ↓
进入正常对话，信号积累后 confidence 逐步提升
```

### 文件存储结构

```
~/.huaqi/data/{user}/telos/
├── beliefs.md          # frontmatter + 当前认知 + 更新历史
├── models.md
├── narratives.md
├── goals.md
├── challenges.md
├── strategies.md
├── learned.md
├── shadows.md
├── meta.md             # 纠错记录、维度操作日志、活跃维度列表
├── INDEX.md            # 自动生成的索引（供人类阅读，不用于 prompt 注入）
├── _archive/           # 归档维度
└── people/             # People 子系统独立目录
    ├── {person_id}.md
    └── ...
```

### 关键待实现项（优先级排序）

1. **接入 Agent**：在 `chat_nodes.py` 的 `build_context` 节点读取维度文件，组装 System Prompt
2. **接入自动提炼**：在 scheduler 中添加 `DistillationJob`，定期处理未处理的 RawSignal
3. **合并 Step3/4/5**：重构 `TelosEngine`，将三步合并为一次 LLM 调用
4. **多维度并行**：在 `DistillationPipeline` 中并行执行多个维度的处理
5. **PeoplePipeline 接入**：在 Step1 分叉后调用 `PeoplePipeline`
6. **Person 模型扩展**：添加 `InteractionLog` 和 `EmotionalTimeline`
7. **置信度重构**：改为 `count_score * 0.4 + consistency_score * 0.6`
8. **定时复审任务**：检查长期无信号的维度，触发轻量 LLM 复审
9. **冷启动问卷**：实现5问问卷 + 一次性批量写入逻辑
10. **真实 LLM 集成测试**：用真实 LLM 跑一遍端到端流程，验证 prompt 设计
