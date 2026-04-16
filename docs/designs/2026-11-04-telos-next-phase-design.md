# Telos 下一阶段设计：7 条已知未实现项

**Date:** 2026-11-04
**前置文档：** `2026-10-04-telos-design-and-implementation.md`
**背景：** 本文档记录 Telos 重构验收后，`9.2 暂未实现的设计项` 中 7 条未实现项的详细设计与实施路线。

---

## 7 条未实现项总览

| # | 项目 | 来源 | 依赖 |
|---|------|------|------|
| 1 | 多维度并行执行（asyncio） | 验收清单 9.2 | step345_combined 已稳定 |
| 2 | `search_memory` 工具注入 | 验收清单 9.2 | RawSignal 向量检索 |
| 3 | `search_person` 工具注入 | 验收清单 9.2 | tools.py 已实现，差 build_context 注入 |
| 4 | PeoplePipeline 完整实现 | 验收清单 9.2 | 依赖 5+6 |
| 5 | `Person.InteractionLog` 字段 | 验收清单 9.2 | 无前置依赖 |
| 6 | `Person.EmotionalTimeline` 字段 | 验收清单 9.2 | 无前置依赖 |
| 7 | `PeopleGraph.get_top_n(strategy="freq+emotion")` | 验收清单 9.2 | 依赖 5+6 数据填充 |

---

## 依赖关系图

```
5（InteractionLog） ──┐
                      ├──→ 4（PeoplePipeline）
6（EmotionalTimeline）┘
       ↓
7（get_top_n）→ Agent 上下文注入 People 数据（build_context）

3（search_person 注入）── 独立，tools.py 已实现
2（search_memory 工具）── 独立，需新建 tool

1（asyncio 全链路）── 最后做，依赖整条链路稳定
```

---

## 实施路线

### Week 1：People 数据层（第 5+6+7 条）

#### 第 5+6 条：Person 模型扩展

新增两个 dataclass 到 `people/models.py`：

```python
@dataclass
class InteractionLog:
    date: str               # ISO 格式 "2026-10-01"
    signal_id: str          # 关联 RawSignal ID
    interaction_type: str   # 合作/冲突/日常/初识/久未联系
    summary: str

@dataclass
class EmotionalTimeline:
    date: str
    score: float            # -1.0 ~ 1.0
    trigger: str
```

`Person` dataclass 新增字段：

```python
interaction_logs: List[InteractionLog] = field(default_factory=list)
emotional_timeline: List[EmotionalTimeline] = field(default_factory=list)
```

**存储方式：** 内嵌在 `Person.md` 文件末尾，以 Markdown 表格追加。保留最近 **50 条**，超出时旧记录自动截断（不删除，追加到 `_archive/` 目录下的年度归档文件）。

**Person.md 格式扩展：**

```markdown
## 互动记录
| 日期 | 类型 | 摘要 | signal_id |
|------|------|------|-----------|
| 2026-10-01 | 合作 | 讨论产品方向 | sig_abc123 |

## 情感时序
| 日期 | 分值 | 触发原因 |
|------|------|---------|
| 2026-10-01 | 0.7 | 合作顺畅，共识多 |
```

**PeopleGraph 改动：**
- `_parse_person_md()` 新增解析 `## 互动记录` 和 `## 情感时序` section
- `_serialize_person()` 新增序列化上述两个 section
- 写入时自动裁剪至最近 50 条，超出部分 append 到 `people/_archive/{person_id}_{year}.md`

#### 第 7 条：PeopleGraph.get_top_n

```python
def get_top_n(self, user_id: str, n: int = 5) -> List[Person]:
    people = self.list_people(user_id)

    def score(p: Person) -> float:
        freq_score = min(len(p.interaction_logs) / 50, 1.0)
        if p.emotional_timeline:
            latest_emotion = abs(p.emotional_timeline[-1].score)
        else:
            latest_emotion = abs(p.emotional_impact)  # fallback
        return freq_score * 0.5 + latest_emotion * 0.5

    return sorted(people, key=score, reverse=True)[:n]
```

**评分公式：** `freq_score * 0.5 + latest_emotion_intensity * 0.5`
- `freq_score`：`min(len(interaction_logs) / 50, 1.0)`，归一化互动频率
- `latest_emotion_intensity`：最近一条 EmotionalTimeline 的 `abs(score)`，捕捉关系近期变化
- 情感用「最近一条」而非平均值，使 Agent 对新发生的关系变化更敏感

---

### Week 2：PeoplePipeline 完整实现（第 4 条）

**文件：** `huaqi_src/layers/growth/telos/dimensions/people/pipeline.py`

**流程：**

```
PeoplePipeline.process(signal, mentioned_names)
  ↓
LLM 提取（1次调用）：
  输入：信号原文 + 已有人物信息摘要
  输出：
    - person_name
    - emotional_score: float (-1.0~1.0)
    - interaction_type: 合作/冲突/日常/初识/久未联系
    - summary: str
    - new_attributes: dict（职位变化、新标签等）
  ↓
PeopleGraph.merge()（无 LLM）：
  - 已有人物 → 追加 InteractionLog + EmotionalTimeline
  - 新人物 → 创建 Person，打初始标签
```

**与 DistillationPipeline 的接入点：**

`pipeline.py` 的 Step1 之后已有 `if step1_result.has_people and self._person_extractor` 的分叉逻辑（验收清单 4.3 已实现）。本阶段将 `PersonExtractor` 替换为完整的 `PeoplePipeline`（见空白 1 的说明）。

---

### Week 3：Agent 工具层（第 2+3 条）

#### 第 3 条：search_person 注入（极低改动）

`tools.py` 里 `search_person_tool` 已实现并注册到 `_TOOL_REGISTRY`，但 `chat_nodes.py` 的 `build_context` 节点未将其放入 `bind_tools` 的工具列表。

**改动：** 在 `chat_nodes.py` 工具注册处加入 `search_person_tool`。

#### 第 2 条：search_memory 工具

**语义：** 检索 **RawSignal 原始内容**（用户写的日记/笔记原文），向量检索。

与现有工具的区分：
- `search_memory(query)` → RawSignal 原文（本条）
- `search_person(name)` → 人物完整画像
- `search_huaqi_chats_tool` → 聊天记录

**注意：** 此条有前置工程依赖，见空白 2 的说明，建议从 Week 3 移出单独排期。

---

### Week 4：asyncio 全链路改造（第 1 条）

**改造范围：**

| 文件 | 改动 |
|------|------|
| `TelosEngine.step345_combined` | `async def`，LLM 调用改 `.ainvoke()` |
| `DistillationPipeline.process` | `async def`，`for` 循环改 `asyncio.gather(*tasks)` |
| `DistillationJob.run_distillation_job` | `async def`，入口用 `asyncio.run()` |
| `ReviewJob.run_review_job` | `async def` |
| `TelosManager.update` / `PeopleGraph` 写入 | 确认文件写入无竞态（不同维度写不同文件，安全；共享 `meta.md` 需加 `asyncio.Lock`） |

**并行粒度：** Step1 串行（确定涉及哪些维度），Step1 完成后各维度的 `step345_combined` 并行，People 处理与维度处理同级并行。

```python
async def process(self, signal):
    step1_result = await self._engine.step1(signal)

    tasks = [
        self._engine.step345_combined(dim, ...)
        for dim in step1_result.dimensions
    ]
    if step1_result.has_people and self._people_pipeline:
        tasks.append(self._people_pipeline.process(signal, step1_result.mentioned_names))

    await asyncio.gather(*tasks)
```

**LangChain 兼容性：** LangChain 原生支持 `.ainvoke()`，无需额外适配。

---

## 设计决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 多维度并行方案 | asyncio 全链路改造 | 与 LangChain/LangGraph async 生态对齐，比 ThreadPoolExecutor 更彻底 |
| InteractionLog/EmotionalTimeline 存储 | 内嵌 Person.md，保留最近 50 条 | 与 Telos 维度文件设计模式一致，无需引入新存储机制 |
| 历史超限处理 | 超出 50 条归档到 `_archive/` | 数据不丢失，主文件保持轻量 |
| get_top_n 情感取值 | 最近一条 EmotionalTimeline | 对新发生的关系变化更敏感，符合 Agent 当前对话场景需求 |
| get_top_n 评分公式 | `freq * 0.5 + emotion * 0.5` | 两者等权，可后续通过参数调整权重 |
| search_memory 语义 | 检索 RawSignal 原始内容 | 与 search_person（画像）、search_huaqi_chats（聊天记录）三者语义不重叠 |
| 实施顺序 | People 数据层 → Pipeline → Agent 工具 → asyncio | 依赖链自底向上，每个阶段产出可独立验证 |

---

## 补充：3 处空白的代码现状核查（2026-11-04）

### 空白 1：PeoplePipeline 与 PersonExtractor 的关系

**PersonExtractor 现状（`people/extractor.py`）：**

`extract_from_text(text) -> list[Person]` 提取的是**静态画像**，LLM 输出结构为：

```json
{
  "name": "张伟",
  "relation_type": "同事",
  "profile": "产品经理，务实",
  "emotional_impact": "积极",
  "alias": ["小张"]
}
```

**问题：** `emotional_impact` 是字符串枚举（积极/中性/消极），无数值；没有 `interaction_type`、`summary`、`signal_id` 字段。PersonExtractor 无法直接扩展为 PeoplePipeline，需要**重新设计 prompt 和输出结构**。

**PeoplePipeline 新 Prompt 设计（Week 2 需实现）：**

输入：
- 信号原文
- 已有人物列表摘要（name + relation_type + profile 前50字）

LLM 输出结构（新增）：

```json
[
  {
    "name": "张伟",
    "interaction_type": "合作",
    "emotional_score": 0.6,
    "summary": "一起推进了产品评审，共识较多",
    "new_profile": null,
    "new_relation_type": null
  }
]
```

**与 PersonExtractor 的关系：** PeoplePipeline 内部不复用 PersonExtractor。PersonExtractor 负责「新人物初次建档」（从文本提取静态画像），PeoplePipeline 负责「已知人物追加互动记录」。两者职责分离，PeoplePipeline 在处理时先判断人物是否已存在：
- 已存在 → 只追加 InteractionLog + EmotionalTimeline，可选更新 profile
- 不存在 → 调用 PersonExtractor 建档，再追加首次互动记录

---

### 空白 2：search_memory 的前置工程

**RawSignalStore 现状：** 完全不支持向量搜索。方法列表为 `save / get / query / mark_processed / mark_distilled / mark_vectorized / count`。`RawSignal` 模型只有 `vectorized: bool` 标志位，**无 embedding 字段，无向量检索方法**。

**结论：** `search_memory` 工具是一个**独立的前置工程**，Week 3 无法直接实现，需要先完成：

1. `RawSignal` 模型新增 `embedding: Optional[List[float]]` 字段
2. 信号入库时调用 embedding 模型生成向量（或补跑 vectorize job）
3. `RawSignalStore.search_by_embedding(query_vec, top_k)` 向量检索方法
4. `search_memory_tool` 接收 query 文本 → 转 embedding → 调用检索 → 返回原文列表

**建议：** 将 `search_memory` 从 Week 3 中移出，作为独立任务单独排期，不阻塞其他 3 条的进度。

---

### 空白 3：asyncio 改造的测试策略

**当前测试基础设施：**
- `pyproject.toml` 已配置 `asyncio_mode = "auto"`，pytest-asyncio 基础就绪
- 但所有 LLM mock 均为同步方式：`mock_llm.invoke.return_value = MagicMock(...)`
- 仅 `test_chat_nodes.py` 中有 1 个 `@pytest.mark.asyncio` 异步测试作为参考

**Week 4 测试改造范围：**

| 测试文件 | 需要改动 |
|---------|---------|
| `tests/unit/layers/growth/test_telos_engine.py` | `mock_llm.invoke` → `mock_llm.ainvoke`，测试函数改 `async def` |
| `tests/unit/layers/data/test_raw_signal_pipeline.py` | 同上 |
| `tests/integration/test_telos_to_agent.py` | 同上 |
| `tests/integration/test_cold_start.py` | 视改动范围决定 |

**注意事项：**
- `asyncio_mode = "auto"` 已开启，不需要每个测试加 `@pytest.mark.asyncio` 装饰器
- `mock_llm.ainvoke` 需要改为 `AsyncMock`（`from unittest.mock import AsyncMock`），不能用普通 `MagicMock`
- 文件写入（`TelosManager.update`）保持同步即可，直接同步调用（文件 I/O 在此规模下不是瓶颈）
- `meta.md` 并发写入风险：需加 `asyncio.Lock`，在 `TelosManager` 层持有 `_meta_lock: asyncio.Lock`
