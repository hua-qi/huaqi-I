# Telos 重构验收清单

> 本文档用于验收 `2026-10-04-telos-design-and-implementation.md` 所描述的重构内容。
> 每条对应一个可观察的行为或可验证的代码状态。
>
> **答题说明**：✅ 已实现 | ⚠️ 部分实现 | ❌ 未实现 | 🔲 未验证

---

## 一、Agent 上下文注入（Task 1）

### 1.1 TelosManager 维度片段读取

- [ ] `TelosManager.get_dimension_snippet(name)` 方法是否存在？
  > 预期：返回该维度文件的 `frontmatter + ## 当前认知` 部分（截止 `## 更新历史` 分隔符之前）。

- [ ] `get_dimension_snippet` 的返回值是否**不含** `## 更新历史` 及其后的内容？
  > 验证方式：对一个有历史记录的维度调用该方法，检查返回字符串中不含 `## 更新历史`。

- [ ] `TelosManager.get_all_dimension_snippets()` 方法是否存在？
  > 预期：返回 `dict[str, str]`，key 为维度名，value 为该维度的片段内容。

- [ ] `get_all_dimension_snippets` 是否只包含当前活跃维度（不含已归档维度）？
  > 验证方式：归档一个维度后调用，该维度不应出现在返回的 dict 中。

### 1.2 TelosContextBuilder.build_telos_snapshot

- [ ] `build_telos_snapshot()` 是否读取各维度文件而非 `INDEX.md`？
  > 验证方式：更新某维度的 `## 当前认知` 内容后调用，新内容应出现在返回的快照字符串中。

- [ ] 快照内容是否包含所有活跃维度的当前认知（而非30字截断）？
  > 验证方式：写入一段超过30字的维度内容，快照中应包含完整内容。

- [ ] 快照是否排除了 `## 更新历史` 中的历史记录？
  > 验证方式：在更新历史中写入特定字符串，该字符串不应出现在 `build_telos_snapshot()` 的返回值中。

### 1.3 build_context 节点接入

- [ ] `chat_nodes.py` 中是否存在 `_get_telos_manager()` 辅助函数？
  > 预期：返回 `TelosManager` 实例，若 telos 目录不存在则返回 `None`。

- [ ] `build_context()` 是否调用了 `TelosContextBuilder.build_telos_snapshot()`？
  > 验证方式：在 `build_context` 内打断点或查看调用链，确认有 `TelosContextBuilder` 的实例化和调用。

- [ ] 最终生成的 `system_prompt` 是否包含维度内容？
  > 验证方式：为某维度写入特定内容，触发 `build_context`，检查返回的 `workflow_data["system_prompt"]` 中含有该内容。

- [ ] telos 目录不存在时，`build_context` 是否仍能正常返回（不抛异常）？
  > 验证方式：指向一个不存在的 telos 目录，调用 `build_context`，确认不报错。

- [ ] `build_system_prompt` 函数签名是否新增了 `telos_snapshot` 参数？
  > 验证方式：检查函数定义，确认第三个参数为 `telos_snapshot: Optional[str] = None`。

- [ ] `system_prompt` 中 telos 内容是否以 `## 你对这个用户的了解` 为标题注入？
  > 验证方式：检查 `build_system_prompt` 函数体，确认有该标题字符串。

---

## 二、自动提炼触发（Task 2）

### 2.1 DistillationJob

- [ ] `huaqi_src/scheduler/distillation_job.py` 文件是否存在？

- [ ] `run_distillation_job(user_id, limit)` 函数是否存在？
  > 预期：查询 `processed=0` 的信号，逐条调用 `DistillationPipeline.process()`。

- [ ] 有未处理信号时，`run_distillation_job` 的返回值 `processed` 是否等于实际处理数量？
  > 验证方式：预置 N 条 `processed=0` 的信号，调用 `run_distillation_job(limit=N)`，确认返回 `{"processed": N, "errors": 0}`。

- [ ] 无未处理信号时，`run_distillation_job` 是否返回 `{"processed": 0, "errors": 0}`？

- [ ] 单条信号提炼失败时，`errors` 计数是否+1，且不影响其他信号的处理？
  > 验证方式：mock 某条信号的 pipeline 调用抛出异常，确认其余信号正常处理且 `errors=1`。

### 2.2 注册到 Scheduler

- [ ] `huaqi_src/scheduler/jobs.py` 中是否存在 `register_distillation_job()` 函数？

- [ ] `register_distillation_job` 是否以 `job_id="distillation_job"` 注册到 `APSchedulerAdapter`？
  > 验证方式：查看函数体，确认 `add_interval_job` 的 `job_id` 参数值。

- [ ] `register_distillation_job` 的默认触发间隔是否为 `3600` 秒（1小时）？

---

## 三、Step3/4/5 合并与置信度重构（Task 3）

### 3.1 CombinedStepOutput

- [ ] `engine.py` 中是否存在 `CombinedStepOutput` 类？
  > 预期：Pydantic 模型，包含 `should_update / new_content / consistency_score / history_entry / is_growth_event / growth_title / growth_narrative / confidence` 字段。

- [ ] `confidence` 字段是否有默认值 `0.0`（由代码计算而非 LLM 直接输出）？
  > 验证方式：检查 `CombinedStepOutput` 的字段定义，确认 `confidence: float = 0.0`。

### 3.2 step345_combined 方法

- [ ] `TelosEngine.step345_combined()` 方法是否存在？
  > 预期：接受 `dimension / signal_summaries / days / recent_signal_count`，只调用一次 LLM。

- [ ] `step345_combined` 是否只调用了**一次** `self._llm.invoke()`？
  > 验证方式：在测试中统计 `mock_llm.invoke.call_count`，应为 1。

- [ ] 置信度计算是否遵循 `count_score * 0.4 + consistency_score * 0.6` 公式？
  > 验证方式：传入 `recent_signal_count=5`，`consistency_score=0.8`，计算期望值 `min(5/10,1.0)*0.4 + 0.8*0.6 = 0.68`，确认 `result.confidence ≈ 0.68`。

- [ ] `count_score` 的上限是否为 `1.0`（即 `min(recent_count/10, 1.0)`）？
  > 验证方式：传入 `recent_signal_count=20`，确认 `count_score` 不超过 1.0。

- [ ] `should_update=True` 时，`step345_combined` 是否自动调用 `TelosManager.update()`？
  > 验证方式：调用后检查 `telos_manager.get(dimension).update_count == 1`。

- [ ] `should_update=False` 时，`step345_combined` 是否**不**修改维度文件？
  > 验证方式：mock 返回 `should_update=False`，调用后确认 `update_count` 仍为 0。

- [ ] 写入 `HistoryEntry` 时，`confidence` 是否用计算值而非 LLM 的原始输出？
  > 验证方式：检查 `HistoryEntry.confidence` 等于 `step345_combined` 计算出的 `result.confidence`。

### 3.3 DistillationPipeline 使用新方法

- [ ] `DistillationPipeline.process()` 是否改为调用 `step345_combined` 而非原有的 `run_pipeline`（分开的 step3/4/5）？
  > 验证方式：检查 `pipeline.py`，确认循环内不再调用 `engine.step3_decide + step4_generate + step5_judge_growth`。

- [ ] `step345_combined` 调用时，`recent_signal_count` 是否来自 `RawSignalStore.count()` 的实际统计值？
  > 验证方式：检查 `pipeline.py` 中 `step345_combined` 的调用，确认 `recent_signal_count` 参数来自 store 查询。

- [ ] `is_growth_event=True` 时，成长事件是否正确存入 `GrowthEventStore`（含 `growth_title` 和 `growth_narrative`）？
  > 验证方式：mock `combined_result.is_growth_event=True`，调用后查询 `event_store.list_by_user()`，确认事件存在且标题正确。

---

## 四、People 维度独立化（Task 4）

### 4.1 从 STANDARD_DIMENSIONS 移除

- [ ] `STANDARD_DIMENSIONS` 列表是否不含 `"people"`？
  > 验证方式：`assert "people" not in STANDARD_DIMENSIONS`。

- [ ] `STANDARD_DIMENSIONS` 的长度是否为 8？

- [ ] `STANDARD_DIMENSION_LAYERS` 字典是否不含 `"people"` 键？

- [ ] `TelosManager._INITIAL_CONTENT` 字典是否不含 `"people"` 键？
  > 验证方式：检查 `manager.py`，确认初始内容字典中无 `people` 条目。

- [ ] `TelosManager.init()` 执行后，telos 目录下是否不再创建 `people.md` 文件？
  > 验证方式：在 tmp 目录执行 `mgr.init()`，确认目录中无 `people.md`。

- [ ] 原有依赖 `people` 维度的测试是否已全部更新（无残留失败）？
  > 验证方式：运行 `pytest tests/unit/layers/growth/ -v`，全部 PASSED。

### 4.2 Step1 Output 支持 has_people / mentioned_names

- [ ] `Step1Output` 是否新增了 `has_people: bool = False` 字段？

- [ ] `Step1Output` 是否新增了 `mentioned_names: List[str]` 字段（默认空列表）？

- [ ] `_STEP1_PROMPT` 中是否要求 LLM 输出 `has_people` 和 `mentioned_names` 字段？
  > 验证方式：查看 prompt 文本，确认 JSON 模板中包含这两个字段。

### 4.3 DistillationPipeline People 分叉

- [ ] `DistillationPipeline.__init__` 是否接受可选的 `person_extractor` 参数？

- [ ] `pipeline.process()` 中，Step1 之后是否有 `if step1_result.has_people and self._person_extractor` 的判断？

- [ ] `step1_result.has_people=True` 且 `person_extractor` 存在时，是否调用 `person_extractor.extract_from_text(signal.content)`？
  > 验证方式：传入 mock extractor，触发 `has_people=True` 的信号，确认 `extract_from_text` 被调用一次。

- [ ] People 处理失败时（extractor 抛异常），是否不影响维度提炼流程继续执行？
  > 验证方式：让 extractor 抛出异常，确认维度侧的 step345_combined 仍正常执行。

- [ ] `person_extractor=None` 时，pipeline 是否正常运行（向后兼容）？

---

## 五、定时复审（Task 5）

### 5.1 review_stale_dimension

- [ ] `TelosEngine.review_stale_dimension(dimension, days_since_last_signal)` 方法是否存在？

- [ ] 该方法是否只调用一次 LLM？

- [ ] `is_stale=True` 时，是否降低对应维度的 `confidence`？
  > 验证方式：mock 返回 `is_stale=True, new_consistency_score=0.4`，调用后检查 `dim.confidence < 原始置信度`。

- [ ] `is_stale=True` 时，降低 confidence 的公式是否为 `count_score * 0.4 + new_consistency_score * 0.6`？

- [ ] `is_stale=False` 时，维度 `confidence` 是否保持不变？

- [ ] 复审写入的 `HistoryEntry.trigger` 是否包含 `"天无新信号"` 等提示复审原因的文字？

- [ ] 返回值是否为 `ReviewOutput` 类型（含 `is_stale / new_consistency_score / reason`）？

### 5.2 ReviewJob

- [ ] `huaqi_src/scheduler/review_job.py` 文件是否存在？

- [ ] `run_review_job(stale_threshold_days)` 函数是否存在？

- [ ] 维度的 `updated_at` 距今超过 `stale_threshold_days` 时，是否触发 `engine.review_stale_dimension()`？
  > 验证方式：mock `_get_dimension_last_updated` 返回35天前的日期，`stale_threshold_days=30`，确认 engine 方法被调用。

- [ ] 返回值是否含 `reviewed`（已复审数量）和 `stale_found`（发现过时数量）？

- [ ] 单个维度复审失败时，是否不中断其他维度的复审？
  > 验证方式：让某一维度的 engine 调用抛出异常，确认其他维度仍被复审。

---

## 六、冷启动问卷升级（Task 6）

### 6.1 问卷压缩为 5 个问题

- [ ] `ONBOARDING_QUESTIONS` 列表长度是否为 5？

- [ ] 5 个问题是否覆盖设计文档规定的维度组合？
  > 预期覆盖关系：`goals+challenges / beliefs+models / narratives+shadows / strategies+learned / people`

- [ ] 最后一个问题的 `dimension` 是否为 `"people"`？

- [ ] `OnboardingSession.is_complete()` 是否在回答/跳过 5 个问题后返回 `True`？

- [ ] 相关测试（`TestOnboardingQuestions / TestOnboardingSession`）是否已同步更新为期望 5 个问题？
  > 验证方式：运行 `pytest tests/integration/test_cold_start.py -v`，全部 PASSED。

### 6.2 初始置信度 0.4

- [ ] `OnboardingTelosGenerator.generate()` 中，写入维度时 `confidence` 是否为 `0.4`？
  > 验证方式：检查 `telos_generator.py`，确认 `confidence=0.4`（而非旧的 `0.5`）。

- [ ] `HistoryEntry` 中记录问卷初始化的 `confidence` 是否也为 `0.4`？

- [ ] 相关测试中对 `confidence` 的断言是否已更新为 `== 0.4`？
  > 验证方式：`pytest tests/integration/test_cold_start.py::TestOnboardingTelosGenerator -v`，全部 PASSED。

---

## 七、端到端真实 LLM 验证（Task 7）

### 7.1 e2e 测试文件

- [ ] `tests/e2e/test_telos_e2e.py` 文件是否存在？

- [ ] `pyproject.toml` 中是否注册了 `e2e` marker？
  > 验证方式：查看 `[tool.pytest.ini_options].markers`，确认有 `e2e` 条目。

- [ ] `test_step1_real_llm_parses_journal` 是否在有效 LLM 配置下通过？
  > 预期：`Step1Output.dimensions` 不为空，且含 `challenges/goals/beliefs` 之一。

- [ ] `test_step345_combined_real_llm` 是否在有效 LLM 配置下通过？
  > 预期：`result.confidence` 在 `[0.0, 1.0]` 范围内，`consistency_score` 同上。

- [ ] `test_telos_snapshot_in_agent_context_real_llm` 是否在有效 LLM 配置下通过？
  > 预期：触发 `step345_combined` 后，`build_telos_snapshot()` 的返回值中包含 `"beliefs"`。

- [ ] 运行 `pytest tests/unit/ tests/integration/ -v -m "not e2e"` 时，e2e 测试是否被正确跳过（不干扰常规测试套件）？

---

## 八、回归与兼容性

### 8.1 原有流水线测试

- [ ] `pytest tests/unit/layers/growth/test_telos_engine.py -v` 是否全部 PASSED？
  > 包含原有 Step1/3/4/5 的单元测试，不应因新增 `step345_combined` 而破坏。

- [ ] `pytest tests/integration/test_raw_signal_to_telos.py -v` 是否全部 PASSED？
  > 原有集成测试场景（3天日记触发更新）不应因 pipeline 修改而失败。

- [ ] `pytest tests/integration/test_telos_to_agent.py -v` 是否全部 PASSED？
  > 原有 `TelosContextBuilder` 的集成测试应在 `build_telos_snapshot` 修改后仍通过。

### 8.2 cold start 回归

- [ ] `pytest tests/integration/test_cold_start.py -v` 是否全部 PASSED？
  > 问卷逻辑修改后，已更新的测试应全部通过。

### 8.3 Agent 节点回归

- [ ] `pytest tests/unit/agent/test_chat_nodes.py -v` 是否全部 PASSED？
  > `build_context` 修改后，原有的 `retrieve_memories` 等测试不应受影响。

### 8.4 全量测试

- [ ] `pytest tests/ -v --ignore=tests/e2e/` 是否全部 PASSED（或只有预期的 skip）？

---

## 九、设计符合性检查

### 9.1 设计文档中明确的行为约束

- [ ] `system_prompt` 中 Telos 注入部分是否读取 `frontmatter + ## 当前认知`，而非 INDEX.md？
  > 对应设计文档第6节：「各维度读取 frontmatter + ## 当前认知，跳过 ## 更新历史」。

- [ ] `people` 是否已从 `STANDARD_DIMENSIONS` 中移除，不再参与 `TelosEngine` 的5步提炼？
  > 对应设计文档第3节：「people 从8个维度中移除，作为 Telos 下的独立子系统」。

- [ ] 置信度计算是否完全由代码计算（LLM 只输出 `consistency_score`）？
  > 对应设计文档第5节：「confidence = count_score * 0.4 + consistency_score * 0.6」，LLM 不直接输出最终 confidence 数字。

- [ ] 冷启动初始置信度是否为 `0.4`（而非之前的 `0.5`）？
  > 对应设计文档第7节：「初始置信度统一设为 0.4（标记为"问卷初始化，待验证"）」。

- [ ] 冷启动问卷是否为 5 个问题（而非之前的 10 个）？
  > 对应设计文档第7节：「5个问题的问卷」。

### 9.2 暂未实现的设计项（本次范围外）

以下内容在设计文档中提及，但**不在本次重构范围**内，验收时确认其状态为「已知未实现」即可：

- [ ] 多维度并行执行（asyncio）：`step345_combined` 目前仍为串行；并行化为后续优化项。
- [ ] `search_memory` / `search_person` 工具注入：AI 主动调用记忆检索；需 LangGraph tools 集成，不在本次范围。
- [ ] People 子系统完整 `PeoplePipeline`：本次仅实现从 pipeline 分叉调用 `PersonExtractor`；完整的 `InteractionLog / EmotionalTimeline` 扩展为下一阶段。
- [ ] `Person` 模型新增 `InteractionLog` 和 `EmotionalTimeline` 字段：下一阶段实现。
- [ ] `PeopleGraph.get_top_n(strategy="freq+emotion")` 方法：在 Agent 上下文注入 People 数据；下一阶段。

---

**文档版本**：v1.0
**创建时间**：2026-10-04
**对应设计文档**：`docs/designs/2026-10-04-telos-design-and-implementation.md`
**对应实现计划**：`docs/plans/2026-10-04-telos-refactor.md`
**用途**：Telos 重构功能验收，每条对应一个可观察的行为或可验证的代码状态
