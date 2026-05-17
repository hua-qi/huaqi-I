# Spec: 提示词体系重构

## 1. 要解决的问题

当前项目共 44 处 LLM 提示词，硬编码散落在 12+ 个 Python 源文件中。
改一个提示词需要：
1. 找到对应源文件中的字符串
2. 编辑 Python 代码
3. 重启进程才能生效

这导致三个痛点：
- **不可热更新**：调 prompt 必须改代码+重启，无法快速迭代实验
- **组织零散**：提示词隐没在业务逻辑中，难以全局审视 prompt 之间的关系
- **人格分裂**：各模块各自定义 Huaqi 的角色，内容互相独立，缺乏一致的"人格基线"，也不感知 TELOS 对用户的认知

核心目标：**让提示词可独立管理、热更新、围绕 TELOS 建立统一人格。**

## 2. 功能范围

**包含：**
- 在数据目录下建立 `prompts/` 目录，**目录结构镜像源码目录**（`prompts/layers/growth/telos/engine.md` 对应 `huaqi_src/layers/growth/telos/engine.py`）
- 每个提示词一个 `.md` 文件，用 `---` 水平线分隔 `[SYSTEM]` 和 `[USER]` 两部分
- 文件头部用 `<!-- -->` HTML 注释声明元数据（场景、描述、所需变量）
- 支持模板变量（如 `{telos_snapshot}`、`{user_profile}`），运行时 `str.format()` 注入上下文
- 每次 LLM 调用时从文件系统读取最新内容，实现热更新
- **统一角色基线 `base.md`**：围绕 TELOS 维度和用户成长定义 Huaqi 核心人格，所有场景 prompt 共享/引用
- 内置提示词通过初始化流程拷贝到数据目录，用户可自由编辑修改

**包含（可发现性）：**
- **`prompts/INDEX.md`**：一个可读索引文件，列出所有提示词文件的对应关系——什么文件影响什么功能、修改后的效果
- **`huaqi prompts list` CLI 命令**：列出所有提示词的 scene ID、文件路径、功能描述

**不包含：**
- Web UI 编辑器（范围过大）
- Prompt 版本历史/回滚（未来可做，本次不涉及）
- A/B 测试框架（未来可做）
- 提示词业务逻辑的大幅重写（本次做**组织重构+角色统一**，保持现有 prompt 语义不变）

## 3. 技术选型

### 3.1 文件格式

Markdown + 分隔符约定：

```markdown
<!-- scene: agent.chat | variables: personality_context, user_profile_context, telos_snapshot -->

你是 Huaqi (花旗)，用户的个人 AI 成长伙伴。
...

---

{context}
```

- `<!-- -->` HTML 注释行声明元数据：`scene`（场景标识）、`variables`（逗号分隔的模板变量名）
- `---` 水平线以上为 system prompt，以下为 user prompt
- 无 `---` 则整个文件为 system prompt
- 以 `---` 开头则整个文件为 user prompt（无 system 部分）

### 3.2 目录结构

**镜像源码目录**，路径对应关系：`prompts/<源码相对路径不含 huaqi_src/>.md`

```
<data_dir>/prompts/
├── base.md                                    # 角色基线（无对应源文件，统一定义）
├── agent/
│   └── chat.md                                # → agent/nodes/chat_nodes.py
├── scheduler/
│   ├── jobs.md                                # → scheduler/scheduled_job_store.py（6 个 job prompt）
│   └── job_runner.md                          # → scheduler/job_runner.py
├── layers/
│   ├── growth/
│   │   └── telos/
│   │       ├── engine.md                      # → layers/growth/telos/engine.py（STEP1-5 + combined + stale）
│   │       ├── context.md                     # → layers/growth/telos/context.py（4 种模式）
│   │       └── dimensions/
│   │           └── people/
│   │               ├── extractor.md           # → layers/growth/telos/dimensions/people/extractor.py
│   │               └── pipeline.md            # → layers/growth/telos/dimensions/people/pipeline.py
│   ├── capabilities/
│   │   ├── reports/
│   │   │   ├── morning.md                     # → layers/capabilities/reports/morning_brief.py
│   │   │   ├── daily.md                       # → layers/capabilities/reports/daily_report.py
│   │   │   ├── weekly.md                      # → layers/capabilities/reports/weekly_report.py
│   │   │   ├── quarterly.md                   # → layers/capabilities/reports/quarterly_report.py
│   │   │   └── growth.md                      # → layers/capabilities/reports/growth_report.py
│   │   ├── learning/
│   │   │   └── course.md                      # → layers/capabilities/learning/course_generator.py（4 个 prompt）
│   │   ├── onboarding/
│   │   │   └── telos_generator.md             # → layers/capabilities/onboarding/telos_generator.py
│   │   ├── personality/
│   │   │   ├── engine.md                      # → layers/capabilities/personality/engine.py（to_prompt）
│   │   │   └── updater.md                     # → layers/capabilities/personality/updater.py
│   │   └── world_news_enricher.md             # → layers/capabilities/world_news_enricher.py
│   └── data/
│       ├── profile/
│       │   ├── narrative.md                   # → layers/data/profile/narrative.py
│       │   └── extract.md                     # → layers/data/profile/manager.py（2 处提取 prompt）
│       └── memory/
│           └── relevance.md                   # → layers/data/memory/search/llm_search.py
└── cli/
    └── chat.md                                # → cli/chat.py
```

### 3.3 加载策略

- 每次 LLM 调用时从文件系统读取，无内存缓存（用户选择）
- 文件不存在时回退到代码内置默认值
- 性能影响可忽略（单个文件 < 10KB）

### 3.4 PromptLoader API

```python
from huaqi_src.prompts.loader import PromptLoader

loader = PromptLoader(data_dir)

# 加载某个场景的 prompt（自动拼接 base.md 角色基线）
system, user = loader.load("agent.chat", 
    personality_context="...",
    user_profile_context="...",
    telos_snapshot="...",
)

# 加载定时任务 prompt
system, user = loader.load("scheduler.jobs", job_id="morning_brief", telos_snapshot="...")
```

### 3.5 INDEX.md 可发现性索引

`prompts/INDEX.md` 是一个**可读的提示词全貌地图**，由初始化流程自动生成/更新，告诉用户：

```markdown
# 提示词索引

## 角色基线
| 文件 | 影响的功能 | 修改效果 |
|------|-----------|---------|
| `base.md` | **所有场景** | 改变 Huaqi 的整体人格、语气、行为准则 |

## 对话
| 文件 | 影响的功能 | 修改效果 |
|------|-----------|---------|
| `agent/chat.md` | ChatAgent 对话 (`huaqi chat`) | 改变 Huaqi 的回复风格和职责描述 |
| `cli/chat.md` | CLI 交互模式 | 改变 CLI 中的系统提示词 |

## 定时任务
| 文件 | 影响的功能 | 修改效果 |
|------|-----------|---------|
| `scheduler/jobs.md` | 6 个定时任务的任务描述 | 改变定时任务的 prompt 指令 |
| `scheduler/job_runner.md` | 定时任务执行时的系统提示词 | 改变执行报告/推送时的角色行为 |
...
```

### 3.6 CLI 可发现性命令

```bash
$ huaqi prompts list
场景                      文件                         功能
────────────────────────────────────────────────────────────
base                      base.md                     所有场景的角色基线
agent.chat                agent/chat.md               ChatAgent 对话系统提示词
cli.chat                  cli/chat.md                 CLI 交互模式系统提示词
scheduler.jobs            scheduler/jobs.md            6个定时任务的 prompt
scheduler.job_runner      scheduler/job_runner.md      定时任务执行角色
telos.engine              layers/growth/telos/engine.md  TELOS 信号分析（6步）
...
```

### 3.7 角色基线设计

`base.md` 是**所有场景共享的角色基线**，核心定位：

> Huaqi 是围绕 TELOS 认知维度运作的个人成长伙伴系统。
> 它的价值不是通用 AI 助手，而是**基于对用户 TELOS 认知的持续理解，陪伴用户成长**。

各场景 prompt 通过 `PromptLoader` 自动在 system prompt 前拼接 `base.md` 的角色定义，确保一致性。

## 4. 验收标准

### 4.1 基础设施（PromptLoader）

- [ ] AC-1: `PromptLoader` 能根据 scene 标识找到对应的 `.md` 文件 → `test_loader_finds_file_by_scene`
- [ ] AC-2: `PromptLoader.load()` 正确解析 `<!-- -->` 元数据行，暴露 scene/variables 字段 → `test_loader_parses_metadata`
- [ ] AC-3: 文件被 `---` 分隔时，正确返回 system 和 user 两部分 → `test_loader_splits_system_user`
- [ ] AC-4: 文件无 `---` 时，整体作为 system prompt 返回 → `test_loader_no_separator_is_system_only`
- [ ] AC-5: 文件以 `---` 开头时，整体作为 user prompt 返回（system 为 None）→ `test_loader_separator_at_start_is_user_only`
- [ ] AC-6: 模板变量 `{var_name}` 被正确替换 → `test_template_variable_injection`
- [ ] AC-7: 模板变量缺失时抛出明确异常（而非静默忽略）→ `test_missing_variable_raises`
- [ ] AC-8: 场景文件不存在时回退到内置默认值，不抛异常 → `test_fallback_on_missing_file`
- [ ] AC-9: 修改 `.md` 文件后，下一次 `load()` 立即使用新内容（热更新）→ `test_hot_reload`
- [ ] AC-10: 中文/emoji/特殊 Unicode 字符热加载时正确显示 → `test_unicode_hot_reload`

### 4.2 可发现性

- [ ] AC-11: `prompts/INDEX.md` 文件存在，列出所有提示词与对应功能的映射关系 → `test_index_file_exists`
- [ ] AC-12: `INDEX.md` 包含每个提示词文件的"影响的功能"和"修改效果"列 → `test_index_describes_effect`
- [ ] AC-13: `huaqi prompts list` 命令可执行，列出全部提示词的 scene ID 和功能描述 → `test_cli_prompts_list`
- [ ] AC-14: `huaqi prompts list` 输出包含 `base.md` 角色基线条目 → `test_cli_prompts_list_includes_base`
- [ ] AC-15: 新增 prompt 文件后，`INDEX.md` 自动更新包含新条目 → `test_index_auto_updates`

### 4.3 角色基线

- [ ] AC-16: `base.md` 角色基线文件存在，包含 TELOS 维度和用户成长相关角色定义 → `test_base_file_exists`
- [ ] AC-17: 加载任意场景 prompt 时，system prompt **自动**以 `base.md` 内容开头 → `test_base_prepended_to_system`
- [ ] AC-18: `base.md` 角色基线中明确定义 Huaqi 与 TELOS 五大维度的关系（核心层/中间层/表面层）→ `test_base_references_telos_dimensions`
- [ ] AC-19: 用户修改 `base.md` 后，所有场景的 system prompt 都反映新角色定义 → `test_base_hot_reload_propagates`

### 4.4 首次初始化

- [ ] AC-20: 首次启动时，`prompts/` 目录自动创建并以内置默认值填充 → `test_prompts_auto_init`
- [ ] AC-21: 已有 `prompts/` 目录时，不覆盖用户已修改的文件 → `test_auto_init_preserves_user_edits`
- [ ] AC-22: 内置新增了 prompt 文件但用户目录缺失时，补充缺失文件（不覆盖已有）→ `test_auto_init_adds_new_files_only`

### 4.5 各场景迁移

- [ ] AC-23: ChatAgent（`agent/nodes/chat_nodes.py`）使用 `PromptLoader` 加载 prompt → `test_chat_agent_uses_loader`
- [ ] AC-24: 6 个定时任务（`scheduler/`）使用 `PromptLoader` 加载各自 prompt → `test_scheduled_jobs_use_loader`
- [ ] AC-25: TELOS 引擎（`layers/growth/telos/engine.py`）的 6 个 prompt 使用 `PromptLoader` → `test_telos_engine_uses_loader`
- [ ] AC-26: 4 个 Report Agent（morning/daily/weekly/quarterly）使用 `PromptLoader` → `test_reports_use_loader`
- [ ] AC-27: 世界新闻富化（`world_news_enricher.py`）使用 `PromptLoader` → `test_world_news_uses_loader`
- [ ] AC-28: 学习课程生成（`learning/course_generator.py`）的 4 个 prompt 使用 `PromptLoader` → `test_learning_uses_loader`
- [ ] AC-29: 用户画像模块（`data/profile/`）的 narrative + extract prompt 使用 `PromptLoader` → `test_profile_uses_loader`
- [ ] AC-30: 人格模块（`capabilities/personality/`）的 to_prompt + updater prompt 使用 `PromptLoader` → `test_personality_uses_loader`
- [ ] AC-31: 记忆搜索（`data/memory/search/llm_search.py`）的 relevance prompt 使用 `PromptLoader` → `test_memory_search_uses_loader`
- [ ] AC-32: CLI Chat 模式（`cli/chat.py`）使用 `PromptLoader` → `test_cli_chat_uses_loader`
- [ ] AC-33: 人物维度（`telos/dimensions/people/`）的 extractor + pipeline prompt 使用 `PromptLoader` → `test_people_dimension_uses_loader`
- [ ] AC-34: Onboarding 引导（`onboarding/telos_generator.py`）使用 `PromptLoader` → `test_onboarding_uses_loader`

### 4.6 回归保护

- [ ] AC-35: 所有现有冒烟测试（127 用例）继续通过 → 跑 `pytest tests/smoke_test.py -v`
- [ ] AC-36: 所有单元测试继续通过 → 跑 `pytest tests/unit/ -x`
- [ ] AC-37: 迁移后 prompt 语义与原有硬编码 prompt **一致**（仅路径变化，内容不变）→ `test_prompts_match_original`（逐一比对）
- [ ] AC-38: 无硬编码 prompt 残留在 .py 文件中 → `test_no_hardcoded_prompts`

### 4.7 边界情况

- [ ] AC-39: 并发加载同一 prompt 文件时无竞态条件 → `test_concurrent_loads_safe`
- [ ] AC-40: 空文件/纯空白文件被读取时降级为内置默认值 → `test_empty_file_graceful`
- [ ] AC-41: `base.md` 文件被删除后，各场景仍能正常工作（使用内置角色回退）→ `test_missing_base_graceful`

## 5. 依赖

- 依赖已有模块：所有当前使用硬编码 prompt 的模块（scheduler、reports、world_news、chat、telos、learning、profile、memory、personality、onboarding、people）
- 新增模块：`huaqi_src/prompts/loader.py`（PromptLoader）
- 后续 feature 可基于此体系快速添加新 prompt 文件

## 6. 风险与假设

- **风险**：每次调用读文件在极高 QPS 下可能有 IO 开销 —— 当前项目为个人单用户使用，QPS < 1，可忽略
- **风险**：用户手动编辑提示词可能导致格式错误 —— 解析失败时回退到内置默认值
- **风险**：迁移范围广（12+ 源文件），可能遗漏某处硬编码 prompt —— AC-33 自动化检查兜底
- **假设**：用户希望自定义提示词，因此选数据目录而非源码目录。用户会通过编辑器手动编辑 `.md` 文件
