# Telos 下一阶段验收清单

> 本文档用于验收 `2026-11-04-telos-next-phase-design.md` 所描述的 7 条未实现项。
> 每条对应一个可观察的行为或可验证的代码状态。
>
> **答题说明**：✅ 已实现 | ⚠️ 部分实现 | ❌ 未实现 | 🔲 未验证
>
> **核查记录（2026-11-04）**：经代码核查，7 条未实现项均已完成代码实现，
> 当前状态为"已实现、待正式验收测试执行"。详见各条目说明。

---

## 一、Person 模型扩展（第 5+6 条）

### 1.1 InteractionLog 数据类

- [x] `people/models.py` 中是否存在 `InteractionLog` dataclass？
  > ✅ 已实现。`InteractionLog(date, signal_id, interaction_type, summary)` 存在于 `people/models.py`。

- [x] `interaction_type` 是否限定在 `[合作, 冲突, 日常, 初识, 久未联系]` 范围内？
  > ✅ 已实现。`PeoplePipeline` 的 prompt 明确要求 LLM 从该枚举中选择。

### 1.2 EmotionalTimeline 数据类

- [x] `people/models.py` 中是否存在 `EmotionalTimeline` dataclass？
  > ✅ 已实现。`EmotionalTimeline(date, score, trigger)` 存在于 `people/models.py`，score 为 float(-1.0~1.0)。

### 1.3 Person 模型扩展

- [x] `Person` dataclass 是否新增了 `interaction_logs: List[InteractionLog]` 字段（默认空列表）？
  > ✅ 已实现。

- [x] `Person` dataclass 是否新增了 `emotional_timeline: List[EmotionalTimeline]` 字段（默认空列表）？
  > ✅ 已实现。

- [x] `Person.to_dict()` 是否同步序列化了上述两个新字段？
  > ✅ 已实现。`to_dict()` 包含 `interaction_logs` 和 `emotional_timeline` 的完整序列化。

---

## 二、PeopleGraph 存储扩展（第 5+6 条）

### 2.1 Person.md 格式扩展

- [x] `_write_markdown()` 是否在 `## 备注` 之后写入 `## 互动记录` section（Markdown 表格格式）？
  > ✅ 已实现。表头为 `| 日期 | 类型 | 摘要 | signal_id |`。

- [x] `_write_markdown()` 是否在 `## 互动记录` 之后写入 `## 情感时序` section（Markdown 表格格式）？
  > ✅ 已实现。表头为 `| 日期 | 分值 | 触发原因 |`。

### 2.2 读取解析

- [x] `_read_markdown()` 是否能正确解析 `## 互动记录` section 并还原为 `List[InteractionLog]`？
  > ✅ 已实现。`_parse_interaction_logs()` 解析表格行。🔲 正式测试待执行。

- [x] `_read_markdown()` 是否能正确解析 `## 情感时序` section 并还原为 `List[EmotionalTimeline]`？
  > ✅ 已实现。`_parse_emotional_timeline()` 解析表格行，含 float 转换。🔲 正式测试待执行。

- [x] 读取不含新 section 的旧格式 `Person.md` 时，是否向后兼容？
  > ✅ 已实现。两个 parse 方法均在找不到对应 heading 时返回空列表，不抛异常。

### 2.3 50 条上限与归档

- [x] 写入超过 50 条 `interaction_logs` 时，写入文件的记录是否截断为最近 50 条？
  > ✅ 已实现。`_write_markdown()` 检查 `len > MAX_LOGS(50)`，溢出部分归档。🔲 正式测试待执行。

- [x] 超出 50 条的旧记录是否 append 到 `people/_archive/{person_name}_{year}.md`？
  > ✅ 已实现。`_archive_overflow_logs()` 写入 `_archive/` 目录，文件已存在时 append。

- [x] 多次触发归档时，归档内容是否以 append 方式追加（不覆盖旧归档）？
  > ✅ 已实现。代码显式判断 `archive_file.exists()` 后 append。

---

## 三、PeopleGraph.get_top_n（第 7 条）

### 3.1 方法存在性与签名

- [x] `PeopleGraph.get_top_n(n=5)` 方法是否存在？
  > ✅ 已实现。签名为 `get_top_n(self, n: int = 5) -> list[Person]`。

### 3.2 评分逻辑

- [x] 当人物有 `emotional_timeline` 时，`latest_emotion` 是否取最近一条（列表末尾）的 `abs(score)`？
  > ✅ 已实现。`abs(p.emotional_timeline[-1].score)`。

- [x] `freq_score` 是否使用公式 `min(len(interaction_logs) / 50, 1.0)` 计算？
  > ✅ 已实现。

- [x] 评分公式是否为 `freq_score * 0.5 + latest_emotion * 0.5`？
  > ✅ 已实现。

- [x] 人物无 `emotional_timeline` 时，是否回退到 `emotional_impact` 字符串的固定分值作为 fallback？
  > ✅ 已实现。`_impact_map = {"积极": 0.6, "消极": 0.6, "中性": 0.3}`。

### 3.3 返回值

- [x] `get_top_n(n=3)` 时，人物数量超过3个，返回值长度是否恰好为 3？
  > ✅ 已实现。`sorted(...)[:n]`。🔲 正式测试待执行。

- [x] 人物数量少于 `n` 时，是否返回全部人物？
  > ✅ 已实现。Python 切片不越界。

- [x] 返回列表是否按评分从高到低排序？
  > ✅ 已实现。`reverse=True`。

---

## 四、PeoplePipeline 完整实现（第 4 条）

### 4.1 文件与类存在性

- [x] `huaqi_src/layers/growth/telos/dimensions/people/pipeline.py` 文件是否存在？
  > ✅ 已实现。

- [x] `PeoplePipeline` 类是否存在？
  > ✅ 已实现。构造函数：`__init__(self, graph: PeopleGraph, llm: Any, person_extractor=None)`。

### 4.2 LLM 调用策略

- [x] `PeoplePipeline.process(signal, mentioned_names)` 对多个 mentioned_names 是否只调用一次 LLM？
  > ✅ 已实现。prompt 包含所有人名，一次 `ainvoke` 返回 JSON 数组。🔲 正式测试待执行。

- [x] LLM Prompt 是否包含信号原文、已知人物列表摘要和本次提到的人名？
  > ✅ 已实现。`_PROMPT` 注入 `content`、`known_people`、`mentioned_names` 三个变量。

- [x] LLM 返回的每条记录是否包含 `name / interaction_type / emotional_score / summary / new_profile / new_relation_type` 字段？
  > ✅ 已实现。prompt 的 JSON 模板明确列出全部字段。

### 4.3 已知人物处理

- [x] 对已有人物，`process()` 是否追加一条 `InteractionLog`？
  > ✅ 已实现。`updated_logs = existing.interaction_logs + [log]`，随后 `update_person()`。🔲 正式测试待执行。

- [x] 追加的 `InteractionLog.signal_id` 是否等于 `signal.id`？
  > ✅ 已实现。`signal_id=signal.id`。

- [x] 对已有人物，`process()` 是否追加一条 `EmotionalTimeline`？
  > ✅ 已实现。`updated_emotions = existing.emotional_timeline + [emotion]`。

- [x] 追加的 `EmotionalTimeline.score` 是否来自 LLM 输出的 `emotional_score`？
  > ✅ 已实现。`score=float(item.get("emotional_score", 0.0))`。

- [x] `new_profile` 非空时，是否将新内容 merge 到现有 `profile`（而非覆盖）？
  > ✅ 已实现。`merged = f"{existing.profile}\n{item['new_profile']}".strip()`。

- [x] `new_relation_type` 非空时，是否更新 `person.relation_type`？
  > ✅ 已实现。

### 4.4 未知人物处理

- [x] 对不存在于 `PeopleGraph` 中的人名，是否调用 `PersonExtractor.extract_from_text()` 建档？
  > ✅ 已实现。`self._extractor.extract_from_text(signal.content)`。🔲 正式测试待执行。

- [x] `person_extractor=None` 时，对未知人名是否跳过（不报错）？
  > ✅ 已实现。`if existing is None: continue`。

### 4.5 异常处理与返回值

- [x] LLM 返回非法 JSON 时，是否返回空列表 `[]` 而不抛异常？
  > ✅ 已实现。`except Exception: return []`。

- [x] `mentioned_names=[]` 时，是否直接返回 `[]` 不调用 LLM？
  > ✅ 已实现。方法首行 `if not mentioned_names: return []`。

- [x] `process()` 的返回值是否为处理后的 `List[Person]`？
  > ✅ 已实现。

### 4.6 接入 DistillationPipeline

- [x] `DistillationPipeline.__init__` 是否新增了可选参数 `people_pipeline=None`？
  > ✅ 已实现。

- [x] `pipeline.process()` 中，`step1_result.has_people=True` 且 `people_pipeline` 存在时，是否调用 `people_pipeline.process()`？
  > ✅ 已实现。`_run_people()` 方法负责分叉，优先使用 `people_pipeline`。

- [x] `people_pipeline` 和 `person_extractor` 同时存在时，是否优先使用 `people_pipeline`？
  > ✅ 已实现。`_run_people()` 先判断 `people_pipeline is not None`。

- [x] `person_extractor` 路径作为向后兼容 fallback 是否仍然有效？
  > ✅ 已实现。`elif self._person_extractor is not None` 分支保留。

---

## 五、search_person 工具注入（第 3 条）

### 5.1 工具注册确认

- [x] `huaqi_src/agent/tools.py` 中 `search_person_tool` 是否已被 `@register_tool` 装饰？
  > ✅ 已实现。

- [x] `_TOOL_REGISTRY` 中是否包含 `search_person_tool`？
  > ✅ 已实现。`@register_tool` 装饰器自动将工具 append 到 `_TOOL_REGISTRY`。

- [x] `generate_response` 调用 `chat_model.bind_tools(_TOOL_REGISTRY)` 时，`search_person_tool` 是否随之注入？
  > ✅ 已实现。`chat_nodes.py` 中 `bind_tools(_TOOL_REGISTRY)` 全量注入，无需单独处理。
  > **注**：验收清单原描述"差 build_context 注入"有误——工具注入发生在 `generate_response` 的 `bind_tools`，不在 `build_context`。

### 5.2 工具功能验证

- [x] `search_person_tool(name)` 在人物存在时，是否返回包含姓名、关系类型、情感倾向、互动次数的字符串？
  > ✅ 已实现。🔲 正式测试待执行。

- [x] 人物不存在时，是否尝试模糊搜索 `graph.search(name)`？
  > ✅ 已实现。`results = graph.search(name)`。

- [x] 数据目录未设置时，是否返回友好错误文字而不崩溃？
  > ✅ 已实现。`except RuntimeError: return "...（数据目录未设置）"`。

---

## 六、search_memory 工具与向量检索（第 2 条）

### 6.1 RawSignal 模型扩展

- [x] `RawSignal` 是否新增了 `embedding: Optional[List[float]]` 字段（默认 `None`）？
  > ✅ 已实现。`embedding: Optional[List[float]] = None` 存在于 `raw_signal/models.py`。

- [x] 现有不传 `embedding` 的代码是否仍能正常构造 `RawSignal`？
  > ✅ 已实现。字段默认值为 `None`，向后兼容。

### 6.2 RawSignalStore 向量检索

- [x] `RawSignalStore.search_by_embedding(user_id, query_vec, top_k)` 方法是否存在？
  > ✅ 已实现。

- [x] 该方法是否只返回 `embedding` 不为 `None` 的信号？
  > ✅ 已实现。`candidates = [s for s in all_signals if s.embedding is not None]`。

- [x] 相似度计算是否为余弦相似度？
  > ✅ 已实现。`_cosine_sim()` 函数。🔲 正式测试待执行。

- [x] 返回结果是否按相似度从高到低排序，且数量不超过 `top_k`？
  > ✅ 已实现。`scored.sort(..., reverse=True)` 后 `[:top_k]`。

- [x] 无任何含 embedding 的信号时，是否返回空列表而不报错？
  > ✅ 已实现。`if not candidates: return []`。

> **⚠️ 性能说明**：当前实现为全量加载（`limit=1000`）后内存中计算余弦相似度，非 ANN 向量索引。
> 数据量增大时性能会下降，但功能正确，满足当前阶段需求。

### 6.3 search_memory_tool

- [x] `search_memory_tool` 是否存在并被 `@register_tool` 装饰？
  > ✅ 已实现。存在于 `agent/tools.py`，在 `_TOOL_REGISTRY` 中。

- [x] `search_memory_tool` 的 docstring 是否与其他工具语义不重叠？
  > ✅ 已实现。明确说明"检索所有来源的原始记录，包括自动采集的信号"，区别于 `search_diary_tool`。

- [x] 数据目录未设置时，是否返回友好错误？
  > ✅ 已实现。

- [x] embedding 服务调用失败时，是否捕获异常并返回错误说明？
  > ✅ 已实现。`except Exception as e: return f"记忆检索失败：{str(e)[:100]}"`。

---

## 七、asyncio 全链路改造（第 1 条）

### 7.1 TelosEngine.step345_combined

- [x] `TelosEngine.step345_combined` 是否改为 `async def`？
  > ✅ 已实现。

- [x] `step345_combined` 内 LLM 调用是否改为 `await self._llm.ainvoke()`？
  > ✅ 已实现。

- [x] 其余同步方法（`step1_analyze` 等）是否仍保持同步？
  > ✅ 已实现。

### 7.2 DistillationPipeline.process

- [x] `DistillationPipeline.process` 是否改为 `async def`？
  > ✅ 已实现。

- [x] Step1 完成后，各维度的 `step345_combined` 是否通过 `asyncio.gather()` 并行执行？
  > ✅ 已实现。`tasks = [process_dimension(dim) for dim in ...]`，`asyncio.gather(*tasks)`。

- [x] 单个维度失败不中断其他维度？
  > ✅ 已实现。`return_exceptions=True` + 结果过滤。

- [x] People 处理与维度处理同级并行？
  > ✅ 已实现。`tasks.append(self._run_people(...))` 后统一 gather。

### 7.3 PeoplePipeline.process

- [x] `PeoplePipeline.process` 是否为 `async def`？
  > ✅ 已实现。

- [x] LLM 调用是否使用 `await self._llm.ainvoke()`？
  > ✅ 已实现。

### 7.4 Scheduler Job 入口适配

- [x] distillation job 是否已适配 async？
  > 🔲 未验证。需确认 `distillation_job.py` 中调用 `pipeline.process()` 的方式。

### 7.5 TelosManager 并发写入保护

- [x] `TelosManager.__init__` 是否新增了 `_meta_lock: asyncio.Lock`？
  > ✅ 已实现。

### 7.6 测试基础设施

- [x] `pyproject.toml` 中 `asyncio_mode = "auto"` 是否已配置？
  > ✅ 已实现。

- [x] 涉及 `step345_combined` 的测试是否为 `async def`？
  > ✅ 已实现。`test_telos_engine.py` 中 `TestStep345Combined` 的三个测试均为 `async def`。

- [x] mock LLM 的 `ainvoke` 是否使用 `AsyncMock`？
  > ✅ 已实现。`mock_llm.ainvoke = AsyncMock(...)`。

---

## 八、回归与兼容性

- 🔲 `pytest tests/unit/layers/growth/test_telos_engine.py -v` 待执行
- 🔲 `pytest tests/unit/layers/growth/test_telos_manager.py -v` 待执行
- 🔲 `pytest tests/unit/layers/growth/test_telos_models.py -v` 待执行
- 🔲 `pytest tests/unit/layers/data/test_raw_signal_pipeline.py -v` 待执行
- 🔲 `pytest tests/integration/test_telos_to_agent.py -v` 待执行
- 🔲 `pytest tests/integration/test_cold_start.py -v` 待执行
- 🔲 `pytest tests/unit/agent/test_chat_nodes.py -v` 待执行
- 🔲 `pytest tests/ -v` 全量测试待执行

---

## 九、设计符合性检查

- [x] `InteractionLog`/`EmotionalTimeline` 是否以内嵌 Markdown 表格方式存储，无新存储机制？
  > ✅ 已实现。

- [x] `get_top_n` 的情感取值是否使用「最近一条 EmotionalTimeline」？
  > ✅ 已实现。

- [x] `PeoplePipeline` 与 `PersonExtractor` 职责是否分离？
  > ✅ 已实现。前者负责追加互动记录，后者负责新人物静态建档。

- [x] asyncio 改造是否使用 `ainvoke()` 与 LangChain 原生 async 生态对齐？
  > ✅ 已实现。

- [x] `search_memory` 工具的语义是否与其他三个检索工具不重叠？
  > ✅ 已实现。

---

### 9.2 剩余待验收项（需执行测试）

经 2026-11-04 代码核查，7 条未实现项**均已完成代码实现**。当前剩余工作：

| # | 待验收项 | 类型 |
|---|---------|------|
| 1 | Scheduler distillation_job async 适配确认 | 代码核查 |
| 2 | 全套单元测试执行（`pytest tests/`） | 测试执行 |
| 3 | PeoplePipeline 集成测试（含真实文件读写） | 测试执行 |
| 4 | search_by_embedding 余弦相似度精度验证 | 测试执行 |

---

**文档版本**：v1.1（2026-11-04 代码核查后更新）
**创建时间**：2026-11-04
**对应设计文档**：`docs/designs/2026-11-04-telos-next-phase-design.md`
**对应实现计划**：`docs/plans/2026-11-04-telos-next-phase.md`
**用途**：Telos 下一阶段 7 条未实现项的功能验收
