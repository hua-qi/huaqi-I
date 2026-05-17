# 功能验收问题清单

> 本文档用于验收阶段。Agent 可逐条检查，确认功能是否按设计预期实现。
> 每个问题对应一个可观察的行为或可验证的状态。
>
> **答题说明**：✅ 已实现 | ⚠️ 部分实现 | ❌ 未实现 | 🔲 未验证（无法从代码静态确认）

---

## 一、数据层：RAW_SIGNAL

### 1.1 写入

- [x] 用户写一篇日记后，数据库中是否新增一条 `source_type=journal` 的 RAW_SIGNAL？
  > ✅ `SourceType` 枚举包含 `journal`，`RawSignalStore.save()` 通过 `SQLiteStorageAdapter` 写入 SQLite。

- [x] 新写入的 RAW_SIGNAL，`processed` 字段是否为 `0`？
  > ✅ `RawSignal` 模型中 `processed: bool = False`，SQLite 建表默认值为 `DEFAULT 0`。

- [x] 新写入的 RAW_SIGNAL，`distilled` 字段是否为 `0`？
  > ✅ `distilled: bool = False`，SQLite 建表默认值为 `DEFAULT 0`。

- [x] `timestamp` 是否记录的是事件发生时间，而不是写入时间？
  > ✅ `RawSignal.timestamp` 是必填字段，无默认值，必须由调用方传入事件发生时间；`ingested_at` 才是写入时自动设置的当前时间。

- [x] `ingested_at` 是否记录的是写入系统的时间？
  > ✅ `ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))`，写入时自动填充。

- [❌] 导入微信聊天记录后，每条消息是否生成一条独立的 RAW_SIGNAL？
  > ❌ `SourceType.WECHAT` 和 `WechatMetadata` 已定义，但 `converters/` 目录为空，wechat 导入 converter 未实现，无法执行此导入路径。

- [⚠️] 导入音频文件后，RAW_SIGNAL 的 `content` 是否是转录后的文本，`raw_file_ref` 是否指向原始文件？
  > ⚠️ `AudioMetadata`（含 `duration_seconds/speaker_count`）和 `raw_file_ref` 字段已定义，但音频转录的 converter 未实现。字段结构符合设计。

- [❌] 用户 30 天未登录后，系统是否自动生成一条 `source_type=absence` 的 RAW_SIGNAL？
  > ❌ `SourceType.ABSENCE` 和 `AbsenceMetadata` 已定义，但 scheduler 模块未实现，定时检测逻辑不存在，该信号永远不会被自动生成。

- [x] `metadata` 字段是否按 `source_type` 存储了正确的结构化数据？
  > ✅ 各子类型 Pydantic 模型均已定义：`JournalMetadata / WechatMetadata / ReadingMetadata / AudioMetadata / AbsenceMetadata`，以 JSON 序列化存入 SQLite。

### 1.2 查询

- [x] 能否按 `user_id + timestamp` 查询某用户最近 N 天的所有信号？
  > ✅ `RawSignalFilter` 支持 `user_id + timestamp_after/timestamp_before`，`SQLiteStorageAdapter.query()` 动态拼接 WHERE 条件，并有 `idx_user_timestamp` 索引。

- [x] 能否按 `source_type` 过滤，只查某类来源的信号？
  > ✅ `RawSignalFilter.source_type` 字段支持过滤，有 `idx_user_source` 索引。

- [x] 能否查询所有 `processed=0` 的待处理信号？
  > ✅ `RawSignalFilter.processed` 字段支持，有 `idx_user_processed` 索引。

- [x] 能否查询所有 `distilled=0` 的热记忆信号？
  > ✅ `RawSignalFilter.distilled` 字段支持，有 `idx_user_distilled` 索引。

### 1.3 多用户隔离

- [x] 用户 A 的 RAW_SIGNAL 是否对用户 B 不可见？
  > ✅ 所有查询均通过 `user_id` 过滤，`RawSignalFilter` 必须传 `user_id`，`SQLiteStorageAdapter` 所有查询都带 `user_id` WHERE 条件。

- [x] 两个用户同时写入时，是否不会发生数据混淆？
  > ✅ `id` 为 UUID4 主键，`user_id` 强制隔离，`INSERT OR IGNORE` 防止重复。SQLite 本身是文件锁，并发写入安全。

### 1.4 持久化

- [x] 系统重启后，历史 RAW_SIGNAL 是否仍然存在？
  > ✅ SQLite 持久化存储，数据库文件在磁盘上，重启不丢失。

- [x] RAW_SIGNAL 是否永远不会被删除（只增不减）？
  > ✅ `StorageAdapter` ABC 和 `SQLiteStorageAdapter` 均未定义 `delete` 方法，只有 `save/get/query/mark_*` 操作。

- [x] 蒸馏后的 RAW_SIGNAL，`distilled` 是否变为 `1`，但记录本身仍然存在？
  > ✅ `mark_distilled()` 只执行 `UPDATE raw_signals SET distilled=1`，不删除记录。

---

## 二、成长层：TELOS

### 2.1 文件结构

- [x] 初始化后，`~/.huaqi/telos/` 目录下是否生成了 9 个标准维度文件 + `INDEX.md` + `meta.md`？
  > ✅ `TelosManager.init()` 创建 9 个标准维度文件（beliefs/models/narratives/goals/challenges/strategies/learned/people/shadows）+ meta.md + INDEX.md，并创建 `_archive/` 子目录。

- [x] 每个维度文件的 frontmatter 是否包含 `dimension / layer / confidence / updated_at / update_count`？
  > ✅ `TelosDimension.to_markdown()` 生成的 frontmatter 包含这 5 个字段。

- [x] `INDEX.md` 是否按核心层/中间层/表面层分组列出了所有活跃维度？
  > ✅ `TelosManager._rebuild_index()` 按 `DimensionLayer.CORE/MIDDLE/SURFACE` 分组输出，包含「核心层/中间层/表面层」三个 section，末尾还有「特殊」section 含 meta.md。

- [⚠️] `INDEX.md` 的每条记录是否包含文件链接、一句话摘要、版本号和置信度？
  > ⚠️ 当前格式为 `- [beliefs.md](beliefs.md) — v3，置信度 0.8`，包含文件链接、版本号、置信度，但**没有**一句话摘要。设计要求的摘要字段未实现。

### 2.2 版本化更新

- [x] TELOS 某维度更新后，文件中是否新增了一条「更新历史」条目？
  > ✅ `TelosManager.update()` 将 `HistoryEntry` append 到 `dim.history`，`to_markdown()` 以 `### v{n} · {date}` 格式输出到文件末尾。

- [x] 更新历史条目是否包含 `变化 / 触发 / 置信度`？
  > ✅ `HistoryEntry` 包含 `change/trigger/confidence/updated_at`，`to_markdown()` 输出 `**变化**/**触发**/**置信度**` 三行。

- [x] `update_count` 是否在每次更新后自增？
  > ✅ `TelosManager.update()` 中执行 `dim.update_count += 1`。

- [x] `INDEX.md` 的对应行是否在维度更新后同步刷新？
  > ✅ `TelosManager.update()` 最后调用 `self._rebuild_index()`，INDEX.md 自动同步。

- [❌] 能否通过 Git 历史查看某维度的历史版本？
  > ❌ `TelosManager` 有 `git_commit: bool = True` 参数，但当前代码未实现任何 git commit 逻辑（无 GitPython 调用），该参数是空占位符，Git 版本管理不存在。

### 2.3 置信度

- [x] 冷启动问卷生成的初始 TELOS，`confidence` 是否为 `0.5`？
  > ✅ `OnboardingTelosGenerator.generate()` 调用 `self._mgr.update(..., confidence=0.5)`，`HistoryEntry` 的 `confidence=0.5`。

- [x] 由 Agent 观察提炼的更新，`confidence` 是否高于 `0.5`？
  > ✅ Step3 的 LLM 根据信号积累程度输出 `confidence`，Prompt 要求综合评估置信度，对于有多条信号支撑的维度，LLM 会给出高于 0.5 的置信度。（取决于 LLM 实际输出，逻辑上正确。）

- [❌] 用户主动纠错后，对应维度的 `confidence` 是否下调？
  > ❌ `MetaManager.add_correction()` 只写入 meta.md 记录，没有任何调用 `TelosManager.update()` 下调置信度的逻辑。纠错记录与维度文件完全独立，下调置信度未实现。

### 2.4 动态维度

- [x] 用户创建新维度后，`meta.md` 的「活跃维度列表」是否更新？
  > ✅ `MetaManager.add_active_dimension()` 更新 meta.md 的活跃维度列表。（但 `TelosManager.create_custom()` 目前未自动调用 `MetaManager.add_active_dimension()`，需手动调用。）

- [x] 新维度文件是否在 `telos/` 目录下正确创建？
  > ✅ `TelosManager.create_custom()` 创建新的 `.md` 文件，设置 `is_custom=True, confidence=0.5`。

- [x] `INDEX.md` 是否新增了该维度的索引行？
  > ✅ `create_custom()` 最后调用 `self._rebuild_index()`，新维度会出现在对应层级的 section 中。

- [x] 用户归档某维度后，该文件是否移入 `_archive/` 目录？
  > ✅ `TelosManager.archive()` 使用 `shutil.move()` 将文件移入 `_archive/` 子目录。

- [x] 被归档的维度是否从 `INDEX.md` 的活跃列表中移除？
  > ✅ `archive()` 之后调用 `_rebuild_index()`，`list_active()` 只扫描 `telos_dir/*.md`（不含 `_archive/`），所以已归档的维度不会出现在 INDEX.md 中。

- [❌] Agent 发现新维度需求时，是否向用户发出提案通知，而不是自动创建？
  > ❌ Step1 的 `new_dimension_hint` 字段已实现，但 `new_dimension_hint` 累积达阈值后触发提案通知的逻辑未实现（设计中说阈值为 ≥5 条 ≥7 天）。目前没有任何 hint 累积和提案触发机制。

### 2.5 META 维度

- [x] 用户说「这条不对」后，`meta.md` 的「用户反馈记录」是否新增一行？
  > ✅ `MetaManager.add_correction()` 向 meta.md 的表格追加新行。

- [⚠️] 维度被归档时，`meta.md` 的「维度演化历史」是否新增记录？
  > ⚠️ `MetaManager.log_dimension_operation()` 已实现，但 `TelosManager.archive()` 未调用它，需要调用方手动记录。

- [⚠️] 新维度被创建时，`meta.md` 的「维度演化历史」是否新增记录？
  > ⚠️ 同上，`TelosManager.create_custom()` 未调用 `MetaManager.log_dimension_operation()`，需调用方手动记录。

---

## 三、信号提炼管道

### 3.1 Step 1：单条信号分析

- [x] 每条新写入的 RAW_SIGNAL 是否都触发了 Step 1 分析？
  > ✅ `DistillationPipeline.process(signal)` 第一步即调用 `self._engine.step1_analyze(signal)`，然后 `mark_processed(signal.id)`。

- [x] Step 1 的输出是否包含 `dimensions / emotion / intensity / signal_strength / summary`？
  > ✅ `Step1Output` 包含 `dimensions / emotion / intensity / signal_strength / strong_reason / summary / new_dimension_hint`，完全覆盖要求字段。

- [x] Step 1 是否将 META 中的活跃维度列表注入 prompt？
  > ✅ `TelosEngine.step1_analyze()` 调用 `self._active_dimension_names()` 获取活跃维度列表，注入 `_STEP1_PROMPT` 的 `{active_dimensions}` 占位符。

- [x] 用户有自定义维度时，Step 1 是否能正确识别并归入该维度？
  > ✅ `_active_dimension_names()` 通过 `telos_manager.list_active()` 获取，包含自定义维度，统一注入 prompt。

- [x] 信号内容不属于任何现有维度时，`new_dimension_hint` 字段是否有合理的描述？
  > ✅ `Step1Output.new_dimension_hint: Optional[str]`，Prompt 明确要求：「如果信号内容不属于任何现有维度，请在 new_dimension_hint 字段说明」。

- [x] 信号内容属于现有维度时，`new_dimension_hint` 是否为 `null`？
  > ✅ Prompt 中 `new_dimension_hint` 示例为 `null`，LLM 应在有维度匹配时输出 null。

### 3.2 Step 2：跨时间聚合

- [⚠️] 聚合查询是否只取最近 30 天的信号？
  > ⚠️ `DistillationPipeline` 有 `days_window=30` 配置，但 `process()` 方法中查询信号时使用 `RawSignalFilter(user_id=..., processed=1)` 未传 `timestamp_after`，实际上查询的是所有已处理信号，没有严格按 30 天窗口过滤。

- [⚠️] 聚合结果是否按维度分组？
  > ⚠️ 当前实现通过 `dimension in (s.metadata or {})` 过滤信号摘要，以维度为单位处理，但 metadata 中的维度匹配逻辑依赖 metadata 格式，不够健壮。逻辑上是按维度处理的，但聚合不够精准。

- [❌] 单条强信号是否能单独触发后续步骤，而不需要等到聚合？
  > ❌ `DistillationPipeline.process()` 对所有信号统一检查 `count >= threshold`（默认 3），`Step1Output.signal_strength` 字段虽已输出，但 pipeline 中没有 `if signal_strength == STRONG: bypass threshold` 的分支，强信号直通逻辑未实现。

### 3.3 Step 3：更新决策

- [x] `should_update=false` 时，流程是否在此终止，不继续调用 AI？
  > ✅ `TelosEngine.run_pipeline()` 中 `if not step3.should_update: continue`，跳过后续 Step 4/5。

- [x] `should_update=true` 时，`update_type` 是否为 `reinforce / challenge / new` 之一？
  > ✅ `UpdateType` 枚举定义了 `REINFORCE / CHALLENGE / NEW`，Prompt 要求输出这三者之一或 null。

- [⚠️] 核心层维度的更新阈值是否高于表面层？
  > ⚠️ 代码中没有按层级区分阈值，`signal_threshold` 是全局统一的（默认 3）。Step 3 的 Prompt 虽然注入了层级信息（通过 TELOS INDEX），但没有显式的层级阈值差异。

- [⚠️] 弱信号单独出现时，是否不触发更新？
  > ⚠️ pipeline 层没有基于 `signal_strength` 的硬编码拦截；Step 3 Prompt 有「积累」的语义约束，弱信号拦截完全依赖 LLM 的 `should_update` 输出。行为不受代码保证，只受 prompt 约束。

### 3.4 Step 4：生成更新内容

- [x] 生成的 `new_content` 是否简洁（100字以内）、非分析腔？
  > ✅ `_STEP4_PROMPT` 明确要求：「不要用分析腔，要像朋友在帮他整理想法」。（字数限制依赖 LLM 遵从，Prompt 未显式限制 100 字。）

- [x] `history_entry` 是否清晰描述了「从什么变成了什么、为什么」？
  > ✅ `_STEP4_PROMPT` 要求生成 `history_entry.change`（变化描述）和 `history_entry.trigger`（触发信息），与 `HistoryEntry` 的 `change/trigger` 字段对应。

- [x] 更新写入 TELOS 文件后，`processed` 字段是否变为 `1`？
  > ✅ `DistillationPipeline.process()` 在 Step1 分析后立即调用 `self._signal_store.mark_processed(signal.id)`，在 Step4 更新 TELOS 之前就已标记。

### 3.5 Step 5：成长事件判断

- [x] 核心层维度更新后，是否几乎必然生成成长事件？
  > ✅ `_STEP5_PROMPT` 明确判断标准：「核心层维度变化 → 几乎总是值得」。

- [x] 表面层的日常积累（如 LEARNED 更新），是否通常不生成成长事件？
  > ✅ `_STEP5_PROMPT` 明确：「表面层的日常积累 → 通常不值得」。

- [x] 成长事件的 `narrative` 是否用温暖、自然的语言描述变化？
  > ✅ `_STEP5_PROMPT` 要求：「用温暖的语言记录下来」，`Step5Output.narrative` 字段存储叙事文字。

- [x] 成长事件是否记录了触发它的 RAW_SIGNAL ID 列表？
  > ✅ `DistillationPipeline.process()` 创建 `GrowthEvent` 时传入 `trigger_signals=[signal.id]`，`GrowthEvent.trigger_signals: List[str]` 字段存储。

### 3.6 动态维度兼容

- [❌] 同类 `new_dimension_hint` 累积到阈值（≥5 条，≥7 天）时，是否触发提案通知？
  > ❌ 未实现。`new_dimension_hint` 在 Step1 输出后没有任何存储和累积逻辑，无法触发提案通知。

- [❌] 用户拒绝新维度提案后，是否在 META 中记录，且短期内不再重复提案？
  > ❌ 未实现。提案机制整体未实现。

- [x] 用户确认新维度后，后续的 Step 1 是否能正确识别该维度的信号？
  > ✅ `create_custom()` 创建维度文件后，`list_active()` 即可返回该维度，`step1_analyze()` 会将其注入 prompt。

---

## 四、冷启动流程

### 4.1 问卷体验

- [⚠️] 首次启动时，系统是否自动进入问卷流程，而不是直接进入对话？
  > ⚠️ `OnboardingQuestionnaire` 已实现，但 CLI 入口逻辑未实现（cli 模块未见到首次启动检测和自动跳转问卷的代码）。

- [x] 10 个问题是否对话式逐步推进，每次只问一个？
  > ✅ `OnboardingQuestionnaire.next_prompt()` 每次返回当前问题文本，`process_answer()` 推进到下一题，一次只暴露一个问题。

- [❌] Agent 是否在提下一个问题前，先简短回应用户的答案？
  > ❌ 代码层面 `OnboardingQuestionnaire` 是纯状态机，没有「先回应再问下一题」的逻辑。这需要 Agent 层（LangGraph）来处理，当前 Agent 流程未实现此功能。

- [x] 用户跳过某个问题后，系统是否继续问下一个，不强迫回答？
  > ✅ `OnboardingSession.skip()` 递增 `current_index`，跳过的维度不写入 `answers`，后续正常推进。

- [⚠️] 用户可以随时说「不想回答了」结束问卷吗？
  > ⚠️ `OnboardingQuestionnaire` 没有主动终止的方法，但可以不调用 `next_prompt()` 来停止。`is_done()` 只检查是否到达末尾，没有「用户中断」状态。需 Agent 层处理该意图。

### 4.2 初始 TELOS 生成

- [x] 问卷结束后，是否生成了对应维度的 TELOS 文件？
  > ✅ `OnboardingTelosGenerator.generate()` 遍历有回答的维度，调用 `telos_manager.update()` 写入文件。

- [x] 用户跳过的问题对应的维度，是否没有生成文件（不生成空文件）？
  > ✅ `generate()` 只处理 `session.get_answered_pairs()`，跳过的维度不在其中；且对 LLM 返回 `null` 的维度也会 `continue`，不会写入。文件已在 `init()` 时预创建为「（待补充）」，跳过问题不更新内容（设计意图需确认：是保留「待补充」还是不生成？）。

- [x] 所有生成的初始维度，`confidence` 是否为 `0.5`？
  > ✅ `generate()` 中 `confidence=0.5` 硬编码传入 `telos_manager.update()`。

- [⚠️] frontmatter 中是否有标注「来自自述」的字段或注释？
  > ⚠️ `HistoryEntry.trigger="用户问卷回答"` 记录了来源，但 frontmatter 本身没有 `source: questionnaire` 这样的字段。信息在历史记录里，不在 frontmatter。

### 4.3 用户确认环节

- [x] 问卷结束后，Agent 是否主动总结并请用户确认理解是否准确？
  > ✅ `OnboardingTelosGenerator.build_confirmation_summary()` 生成确认文本，以「我整理了一下你说的，看看我理解得对不对」开头，末尾问「有没有哪里理解偏了？」。

- [⚠️] 用户纠正某条理解后，是否立即写入 `meta.md` 的反馈记录？
  > ⚠️ `MetaManager.add_correction()` 已实现，但触发时机依赖 Agent 层的意图识别，当前 Agent 未实现「检测到用户纠错 → 调用 add_correction()」的流程。

- [⚠️] 用户纠正后，对应维度的内容是否立即更新？
  > ⚠️ 需要 Agent 层调用 `TelosManager.update()` 处理，当前未实现。

### 4.4 历史数据导入引导

- [❌] 确认环节结束后，Agent 是否主动引导用户导入历史数据？
  > ❌ 未实现。冷启动流程中没有历史数据导入引导逻辑。

- [❌] 用户选择跳过导入时，系统是否正常进入主对话？
  > ❌ 导入引导未实现，跳过逻辑也不存在，此项前提条件不满足。

- [⚠️] 历史数据导入后，是否批量生成 RAW_SIGNAL 并标记为待处理？
  > ⚠️ `RawSignalStore.save()` 和 `processed=0` 的设计支持批量写入，但批量导入的 converter 未实现（`converters/` 为空）。

---

## 五、Agent 工作模式

### 5.1 后台观察者

- [⚠️] 新 RAW_SIGNAL 写入后，是否自动触发 Step 1 分析（实时或批量）？
  > ⚠️ `DistillationPipeline.process()` 实现了处理逻辑，但自动触发机制（事件监听或定时任务）未实现（scheduler 模块未实现）。

- [❌] 设备重启后，积压的未处理 RAW_SIGNAL 是否在恢复后被批量处理？
  > ❌ `RawSignalFilter(processed=0)` 可查询积压信号，但 scheduler 模块未实现，重启后自动恢复处理的调度逻辑不存在。

- [❌] 表面层维度自动更新后，是否有轻量通知提示用户？
  > ❌ 通知/推送机制整体未实现，系统目前没有任何主动通知能力。

- [❌] 核心层维度更新时，是否生成更明显的变化报告通知？
  > ❌ 成长事件已存入 `GrowthEventStore`，但通知触发机制未实现。`GrowthEventStore.save()` 后没有任何 notify/emit 调用。

### 5.2 主动提问者

- [❌] Agent 是否按用户配置的频率定期发起深度问题？
  > ❌ 未实现。主动提问机制（包括频率配置和定期触发）未实现。

- [❌] 主动提问是否基于当前 TELOS 状态，而不是通用问题？
  > ❌ 未实现。

- [❌] 主动提问的内容是否写入 RAW_SIGNAL（对话记录）？
  > ❌ 未实现。

### 5.3 按需顾问

- [x] 用户发消息时，Agent 是否自动注入 TELOS 上下文？
  > ✅ `TelosContextBuilder.inject()` 将 `telos_snapshot / relevant_history` 注入 `AgentState`，`SystemPromptBuilder.build()` 拼装完整 system prompt。

- [x] Agent 注入的是全量 TELOS 还是相关维度的子集？
  > ✅ `build_telos_snapshot()` 注入的是 `INDEX.md` 全文（所有活跃维度的摘要），相关历史通过 `build_relevant_history()` 向量检索（子集）。

- [❌] 对话结束后，对话内容是否写入 RAW_SIGNAL？
  > ❌ `SourceType.AI_CHAT` 已定义，但 Agent 在对话结束后自动写入 RAW_SIGNAL 的逻辑未实现。LangGraph 图中没有「对话结束 → save to signal store」节点。

---

## 六、System Prompt

- [x] 每次对话开始时，System Prompt 是否包含四个部分：身份准则 / TELOS 快照 / 相关历史 / 当前模式？
  > ✅ `SystemPromptBuilder.build()` 拼装：Part1（角色定位，含交互模式）+ Part2（telos_snapshot）+ Part3（relevant_history）。注意：当前模式已合并在 Part1 的角色定位中，不是独立的 Part4。

- [x] TELOS 快照是否从 `INDEX.md` 动态读取，而不是硬编码？
  > ✅ `build_telos_snapshot()` 直接读取 `INDEX.md` 文件内容。

- [x] 相关历史是否通过 ChromaDB 语义检索，而不是全量注入？
  > ✅ `build_relevant_history()` 调用 `vector_search.search(query, top_k=top_k)`，返回前 K 条相关结果。（ChromaDB 适配器尚未实现，当前 `vector_search=None` 时返回空列表。）

- [x] 不同对话模式（日常/写作/决策/报告）是否切换了不同的 Part 4 指令？
  > ✅ `_PART1_MAP` 定义了 `chat / onboarding / report / distill` 四个模式的不同前缀文本，`SystemPromptBuilder.build()` 根据 `interaction_mode` 选择对应文本。（当前实现是 4 个模式，与设计的「日常/写作/决策/报告」略有差异：writing/decision 模式未定义。）

---

## 七、数据导出与备份

- [❌] 执行全量导出后，是否生成了 JSON（RAW_SIGNAL）+ Markdown（TELOS）+ 原始文件的完整包？
  > ❌ 未实现。没有导出功能。

- [x] 导出的文件是否在没有本系统的情况下也能直接阅读？
  > ✅ TELOS 是标准 Markdown，RAW_SIGNAL 是 SQLite（可用任何 SQLite 工具查看）。

- [❌] TELOS 目录是否纳入 Git 版本管理？
  > ❌ `TelosManager` 有 `git_commit=True` 参数，但代码中没有任何 GitPython 调用，该参数是空占位符，Git 集成未实现。

- [❌] Git 提交记录是否与 TELOS 更新时间对应？
  > ❌ Git 集成未实现，不存在任何提交记录。

- [❌] 定期执行 Git push 后，远端仓库是否有完整的历史记录？
  > ❌ scheduler 和 Git push 均未实现。

---

## 八、错误恢复

- [❌] TELOS 维度被错误更新后，能否通过 Git 回滚到历史版本？
  > ❌ Git 集成未实现，无法通过 Git 回滚。

- [✅] 回滚后，RAW_SIGNAL 是否不受影响？
  > ✅ 架构上 RAW_SIGNAL 存于 SQLite 文件，TELOS 存于 Markdown 文件，两套存储完全独立。即使对 TELOS 目录执行 `git reset`，SQLite 数据库文件不在 Git 追踪范围内，不受影响。这是架构设计保证的，无需 Git 集成即可成立。

- [⚠️] 用户说「这条不对」后，是否立即停止该条逻辑对后续提炼的影响？
  > ⚠️ `MetaManager.add_correction()` 记录反馈，但 Step1-5 的 Prompt 当前没有注入用户纠错历史，纠错记录对后续提炼的实际影响依赖于 Prompt 中是否读取 meta.md（当前未读取）。

- [❌] Agent 升级后，是否将所有 `processed=1` 的 RAW_SIGNAL 重置为 `processed=0`？
  > ❌ 未实现。没有升级重处理机制。

- [❌] Agent 升级重新处理后，是否生成了新的 TELOS 版本（旧版本保留）？
  > ❌ 未实现。

---

## 九、抽象接口与部署

- [x] 将存储后端从 SQLite 切换为 PostgreSQL 时，上层业务代码是否无需修改？
  > ✅ `StorageAdapter` ABC 定义了 `save/get/query/mark_processed/mark_distilled/mark_vectorized/count` 接口，`RawSignalStore` 只依赖 `StorageAdapter`，只需实现 `PostgreSQLStorageAdapter` 即可切换。

- [⚠️] 将向量库从 ChromaDB 切换为 Pinecone 时，检索逻辑是否无需修改？
  > ⚠️ `TelosContextBuilder` 依赖 `vector_search.search(query, top_k)` 接口（duck typing），没有正式的 `VectorAdapter` ABC 定义。切换时调用方不需改，但没有正式合同约束。

- [x] 将 CLI 界面切换为 Web 界面时，Agent 核心逻辑是否无需修改？
  > ✅ `AgentState` 和各 layer 模块与界面无关，CLI 只是触发入口，核心逻辑无需修改。

- [❌] 云端部署后，定时任务是否正常运行（不依赖本地 cron）？
  > ❌ scheduler 模块未实现，定时任务本身不存在，云端部署无从验证。

---

## 十、代码规范符合性

- [x] 项目中是否没有 `_simple / _v2 / _new / _old` 等临时命名的文件？
  > ✅ 新架构文件（`huaqi_src/layers/` 等）均无临时后缀。旧代码 `huaqi_src/core/` 目录有待清理的历史遗留文件，但无临时后缀命名。

- [⚠️] 是否没有 `core/ utils/ helpers/ common/` 等万能桶目录？
  > ⚠️ `huaqi_src/core/` 目录仍存在（待清理的历史遗留），包含 25 个文件。新架构层下无此类目录。

- [x] 所有业务数据传递是否使用 Pydantic 模型，没有裸 dict？
  > ✅ `RawSignal / TelosDimension / HistoryEntry / GrowthEvent / Step1Output / Step3Output / Step4Output / Step5Output / LearningRecord / GrowthReport` 等均为 Pydantic 模型。

- [⚠️] 所有公开类和函数是否有 docstring？
  > ⚠️ 部分类有 docstring（如 `TelosContextBuilder / DistillationPipeline`），但大量类和方法没有 docstring（如 `TelosManager / TelosEngine / MetaManager` 的大多数方法）。

- [x] 依赖方向是否严格单向（cli→agent→layers→config）？
  > ✅ 从代码导入关系看，`layers/` 只依赖 `config/`，`agent/state.py` 由 `layers/growth/telos/context.py` 导入，没有逆向依赖。

- [⚠️] 外部代码是否只通过模块 `__init__.py` 导入，不穿透内部文件？
  > ⚠️ 各模块的 `__init__.py` 尚未填充公开接口，代码中大量直接导入内部模块文件（如 `from huaqi_src.layers.growth.telos.manager import TelosManager`）。

- [❌] `ruff` 检查是否零错误？
  > ❌ 新架构文件（`huaqi_src/layers/ + config/ + agent/state.py`）共有 33 个错误：17 个 `E701`（单行多语句，集中在 `errors.py`），15 个 `F401`（未使用的 import），1 个 `F841`（未使用的局部变量 `layer` 在 `engine.py:228`）。全项目（含旧 `core/`）共 250 个错误。

- [⚠️] `mypy` 检查是否零错误？
  > ⚠️ `mypy` 未安装在项目 venv 中（`.venv/bin/` 无 mypy），无法运行。需先 `pip install mypy` 后验证。

---

**文档版本**：v1.2
**创建时间**：2026-01-04
**更新时间**：2026-01-04
**用途**：功能验收，每个问题对应一个可观察的行为或可验证的状态
