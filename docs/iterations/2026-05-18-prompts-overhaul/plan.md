# Plan: 提示词体系重构

**Goal:** 将所有硬编码 LLM 提示词迁移到数据目录 `prompts/` 下的独立 `.md` 文件，支持热更新、围绕 TELOS 统一人格
**Architecture:** 新增 `huaqi_src/prompts/` 模块（loader + initializer + _defaults），随后逐模块替换硬编码字符串为 PromptLoader 调用
**Spec:** `docs/specs/prompts-overhaul.md`

---

## 背景阅读

实施前必读：
- `docs/specs/prompts-overhaul.md` — 功能规格（41 条 AC）
- `huaqi_src/scheduler/scheduled_job_store.py` — 6 个定时任务 prompt 定义
- `huaqi_src/scheduler/job_runner.py` — job_runner system prompt
- `huaqi_src/layers/growth/telos/engine.py` — TELOS 引擎 6 个 prompt
- `huaqi_src/layers/growth/telos/context.py` — TELOS 上下文 4 种模式 prompt
- `huaqi_src/agent/nodes/chat_nodes.py` — ChatAgent system prompt
- `huaqi_src/layers/capabilities/reports/morning_brief.py` — 晨间简报
- `huaqi_src/layers/capabilities/reports/daily_report.py` — 日终复盘
- `huaqi_src/layers/capabilities/reports/weekly_report.py` — 周报
- `huaqi_src/layers/capabilities/reports/quarterly_report.py` — 季报
- `huaqi_src/layers/capabilities/reports/growth_report.py` — 成长报告
- `huaqi_src/layers/capabilities/world_news_enricher.py` — 世界新闻富化
- `huaqi_src/layers/capabilities/learning/course_generator.py` — 课程生成
- `huaqi_src/layers/capabilities/onboarding/telos_generator.py` — 引导
- `huaqi_src/layers/capabilities/personality/engine.py` — 人格引擎
- `huaqi_src/layers/capabilities/personality/updater.py` — 人格更新
- `huaqi_src/layers/data/profile/narrative.py` — 画像叙事
- `huaqi_src/layers/data/profile/manager.py` — 画像提取
- `huaqi_src/layers/data/memory/search/llm_search.py` — 记忆相关性
- `huaqi_src/layers/growth/telos/dimensions/people/extractor.py` — 人物提取
- `huaqi_src/layers/growth/telos/dimensions/people/pipeline.py` — 人物管道
- `huaqi_src/cli/chat.py` — CLI 对话

运行已有测试确认基线：
```bash
pytest tests/smoke_test.py -v  # 预期 127 passed
pytest tests/ -x --tb=short     # 预期全绿
```

---

## Task 1: PromptLoader 核心引擎

**Files:**
- Create: `huaqi_src/prompts/__init__.py`
- Create: `huaqi_src/prompts/loader.py`
- Create: `huaqi_src/prompts/_defaults.py`
- Create: `tests/unit/prompts/test_loader.py`

### Step 1: 写失败测试

```python
# tests/unit/prompts/test_loader.py
import tempfile
from pathlib import Path

class TestPromptLoader:
    def test_loader_finds_file_by_scene(self):
        """AC-1: PromptLoader 根据 scene ID 找到对应 .md 文件"""
        ...

    def test_loader_parses_metadata(self):
        """AC-2: 正确解析 <!-- --> 元数据"""
        ...

    def test_loader_splits_system_user(self):
        """AC-3: --- 分隔符正确分离 system/user"""
        ...

    def test_loader_no_separator_is_system_only(self):
        """AC-4: 无 --- 时整体作为 system prompt"""
        ...

    def test_loader_separator_at_start_is_user_only(self):
        """AC-5: --- 开头时整体作为 user prompt"""
        ...

    def test_template_variable_injection(self):
        """AC-6: {var_name} 模板变量正确替换"""
        ...

    def test_missing_variable_raises(self):
        """AC-7: 缺失变量抛出异常"""
        ...

    def test_fallback_on_missing_file(self):
        """AC-8: 文件不存在时回退到内置默认值"""
        ...

    def test_hot_reload(self):
        """AC-9: 修改 .md 文件后下次 load() 使用新内容"""
        ...

    def test_unicode_hot_reload(self):
        """AC-10: 中文/emoji 热加载正确显示"""
        ...
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/prompts/test_loader.py -v
```
期望：全部 FAIL（模块尚不存在）

### Step 3: 写实现

创建 `huaqi_src/prompts/loader.py`:

```python
class PromptLoader:
    """从数据目录加载场景提示词，支持模板变量注入和热更新。
    
    文件格式：
        <!-- scene: a.b.c | variables: x, y -->
        system prompt 内容...
        ---
        user prompt 内容...
    """
    
    def __init__(self, prompts_dir: Path):
        self._prompts_dir = prompts_dir
    
    def load(self, scene: str, **kwargs) -> tuple[str | None, str | None]:
        """加载场景 prompt，返回 (system, user)。
        
        - 从文件读取 → 解析元数据 → 分离 system/user → 注入变量
        - 文件不存在时回退到内置默认值
        """
        ...
```

创建 `huaqi_src/prompts/_defaults.py`:
- 从所有现有模块中**逐字提取**当前硬编码的 prompt 字符串
- 组织为 `_BUILTIN_DEFAULTS: dict[str, str]`，key 为 scene ID，value 为完整的 `.md` 内容
- 这是回退机制的基础

创建 `huaqi_src/prompts/__init__.py`:
- 导出 `PromptLoader`、`get_prompt_loader()` 工厂函数

### Step 4: 运行确认通过

```bash
pytest tests/unit/prompts/test_loader.py -v
```
期望：全部 PASS

### Step 5: 更新验收测试

在 `tests/smoke_test.py` 末尾追加：

```python
class TestPromptLoader:
    """prompts-overhaul PromptLoader 验收。
    Spec: docs/specs/prompts-overhaul.md
    """

    def test_loader_initializes_with_prompts_dir(self, tmp_path):
        """AC-1: PromptLoader 能从 prompts 目录初始化."""
        ...

    def test_hot_reload_detects_file_change(self, tmp_path):
        """AC-9: 热更新检测文件变更."""
        ...

    def test_fallback_when_file_missing(self, tmp_path):
        """AC-8: 文件缺失时回退."""
        ...
```

---

## Task 2: PromptInitializer + base.md

**Files:**
- Create: `huaqi_src/prompts/initializer.py`
- Create: `tests/unit/prompts/test_initializer.py`

### Step 1: 写失败测试

```python
# tests/unit/prompts/test_initializer.py

def test_prompts_auto_init(self, tmp_path):
    """AC-20: 首次启动时 prompts/ 目录自动创建并填充默认值"""

def test_auto_init_preserves_user_edits(self, tmp_path):
    """AC-21: 已有 prompts/ 目录时不覆盖用户已修改文件"""

def test_auto_init_adds_new_files_only(self, tmp_path):
    """AC-22: 仅补充缺失的新文件，不覆盖已有"""

def test_base_file_exists(self, tmp_path):
    """AC-16: base.md 角色基线文件存在"""

def test_base_references_telos_dimensions(self, tmp_path):
    """AC-18: base.md 明确定义 Huaqi 与 TELOS 维度的关系"""

def test_base_prepended_to_system(self, tmp_path):
    """AC-17: 加载任意场景 system prompt 自动以 base.md 开头"""

def test_base_hot_reload_propagates(self, tmp_path):
    """AC-19: 修改 base.md 后所有场景反映新角色"""
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/prompts/test_initializer.py -v
```

### Step 3: 写实现

创建 `huaqi_src/prompts/initializer.py`:

```python
class PromptInitializer:
    """负责 prompts/ 目录的首次创建和增量更新。
    
    - 如果 prompts/ 不存在 → 全量创建
    - 如果 prompts/ 存在 → 只补充内置新增但本地缺失的文件
    - 已存在的文件绝不覆盖（保护用户编辑）
    - 自动生成/更新 INDEX.md
    """
    
    def __init__(self, prompts_dir: Path):
        ...
    
    def ensure(self) -> bool:
        """确保 prompts 目录存在且包含所有需要的文件。返回是否有变更。"""
        ...
    
    def rebuild_index(self):
        """重新生成 INDEX.md"""
        ...
```

**base.md 角色基线内容设计：**

```markdown
<!-- scene: base | variables: none -->

你是 Huaqi（花旗），一个围绕 **TELOS 认知维度** 运作的个人 AI 成长伙伴系统。

## 你的本质

你不是一个通用 AI 助手。你的价值在于**基于对用户持续加深的理解，陪伴其成长**。
你对用户的理解建立在 TELOS 维度体系之上：

- **核心认知层（Core）**：用户最底层、最稳定的自我认知——信念、价值观、人生叙
- **中间状态层（Middle）**：正在变化中的认知——当前目标、应对策略、关键关系
- **表面关注层（Surface）**：近期关注的具体事物——技能学习、日常习惯、兴趣波动

你的每一个回应，都应该建立在对这些维度的理解之上。

## 你的行为准则

1. **基于认知回应**：不是泛泛而谈，而是基于你对这个用户具体了解来回应
2. **陪伴成长**：关注用户的长期成长轨迹，而不仅仅是当下问题
3. **适时挑战**：在用户需要成长的时候，温和地提出不同视角
4. **真诚不讨好**：说真话比说好话更重要
5. **简洁有洞察**：不说废话，每一句话都有信息量

## 你的语气

温暖、直接、有洞察力。像一位了解你的老朋友，而不是一位客服。
```

### Step 4: 运行确认通过

```bash
pytest tests/unit/prompts/test_initializer.py -v
```

### Step 5: 更新验收测试

```python
class TestPromptInitializer:
    """prompts-overhaul 初始化验收。"""

    def test_auto_init_creates_prompts_dir(self, tmp_path):
        """AC-20: 自动初始化创建完整目录结构."""
        ...

    def test_preserves_user_modified_files(self, tmp_path):
        """AC-21: 用户编辑过的文件不会被覆盖."""
        ...

    def test_base_content_defines_telos_relationship(self, tmp_path):
        """AC-18: base.md 包含 TELOS 维度关系定义."""
        ...
```

---

## Task 3: 迁移 scheduler 模块

**Files:**
- Modify: `huaqi_src/scheduler/scheduled_job_store.py`
- Modify: `huaqi_src/scheduler/job_runner.py`
- Create: `tests/unit/scheduler/test_job_prompts.py`

### Step 1: 写失败测试

```python
# tests/unit/scheduler/test_job_prompts.py

def test_scheduled_jobs_load_from_loader(self, tmp_path):
    """AC-24: 6个定时任务的 prompt 来自 PromptLoader."""
    # Monkeypatch get_prompt_loader 返回 tmp_path 下的 loader
    # 验证 _build_default_jobs 中的 prompt 字段来自 loader

def test_job_runner_loads_from_loader(self, tmp_path):
    """AC-24: job_runner 使用 PromptLoader 加载 system prompt."""
```

### Step 2: 运行确认失败

### Step 3: 写实现

修改 `scheduled_job_store.py`:
- `_build_default_jobs()` 中每个 job 的 `prompt` 字段改为从 PromptLoader 加载
- 保留 `ScheduledJob.prompt` 字段的语义，但值来自 `loader.load("scheduler.jobs", job_id=...)`

修改 `job_runner.py`:
- `_LEARNING_PUSH_SYSTEM_PROMPT` 常量替换为 `loader.load("scheduler.job_runner", context=...)`
- `_call_llm_for_job()` 中的 fallback system prompt 替换为 loader 调用

### Step 4: 运行确认通过

### Step 5: 更新验收测试

---

## Task 4: 迁移 reports 模块

**Files:**
- Modify: `huaqi_src/layers/capabilities/reports/morning_brief.py`
- Modify: `huaqi_src/layers/capabilities/reports/daily_report.py`
- Modify: `huaqi_src/layers/capabilities/reports/weekly_report.py`
- Modify: `huaqi_src/layers/capabilities/reports/quarterly_report.py`
- Modify: `huaqi_src/layers/capabilities/reports/growth_report.py`
- Create: `tests/unit/layers/capabilities/reports/test_report_prompts.py`

### Step 1: 写失败测试

```python
# tests/unit/layers/capabilities/reports/test_report_prompts.py

def test_morning_brief_uses_loader(self, tmp_path):
    """AC-26: 晨间简报使用 PromptLoader."""

def test_daily_report_uses_loader(self, tmp_path):
    """AC-26: 日终复盘使用 PromptLoader."""

def test_weekly_report_uses_loader(self, tmp_path):
    """AC-26: 周报使用 PromptLoader."""

def test_quarterly_report_uses_loader(self, tmp_path):
    """AC-26: 季报使用 PromptLoader."""
```

### Step 2: 运行确认失败

### Step 3: 写实现

每个 report agent 的 `_generate_xxx()` 方法中：
- 将内联 `system_prompt = "..."` 替换为 `loader.load("layers.capabilities.reports.xxx", ...)`
- 保持 user message（context 注入）逻辑不变

### Step 4: 运行确认通过

### Step 5: 更新验收测试

---

## Task 5: 迁移 TELOS 模块

**Files:**
- Modify: `huaqi_src/layers/growth/telos/engine.py`
- Modify: `huaqi_src/layers/growth/telos/context.py`
- Modify: `huaqi_src/layers/growth/telos/dimensions/people/extractor.py`
- Modify: `huaqi_src/layers/growth/telos/dimensions/people/pipeline.py`
- Create: `tests/unit/layers/growth/telos/test_telos_prompts.py`

### Step 1: 写失败测试

```python
# tests/unit/layers/growth/telos/test_telos_prompts.py

def test_telos_engine_uses_loader(self, tmp_path):
    """AC-25: TELOS 引擎 6 个 prompt 使用 PromptLoader."""

def test_telos_context_uses_loader(self, tmp_path):
    """AC-25: TELOS context 4 种模式使用 PromptLoader."""

def test_people_extractor_uses_loader(self, tmp_path):
    """AC-33: 人物提取使用 PromptLoader."""

def test_people_pipeline_uses_loader(self, tmp_path):
    """AC-33: 人物管道使用 PromptLoader."""
```

### Step 2: 运行确认失败

### Step 3: 写实现

引擎 (`engine.py`):
- 6 个模块级常量 `_STEP1_PROMPT` ~ `_STEP345_COMBINED_PROMPT` + `_REVIEW_STALE_PROMPT` 
- 改为调用 `loader.load("layers.growth.telos.engine", step="step1", ...)`
- 注意：这些 prompt 使用 `.format()` 动态注入 `{telos_index}`, `{signal_summaries}` 等 → 作为模板变量传给 loader

上下文 (`context.py`):
- 4 个模式常量 `_PART1_CHAT` ~ `_PART1_DISTILL`
- 改为 `loader.load("layers.growth.telos.context", mode="chat", ...)`

人物维度 (`extractor.py`, `pipeline.py`):
- `_EXTRACT_PROMPT` 和 `_PROMPT` 改为 loader 调用

### Step 4: 运行确认通过

### Step 5: 更新验收测试

---

## Task 6: 迁移其余模块

**Files:**
- Modify: `huaqi_src/layers/capabilities/world_news_enricher.py`
- Modify: `huaqi_src/layers/capabilities/learning/course_generator.py`
- Modify: `huaqi_src/layers/capabilities/onboarding/telos_generator.py`
- Modify: `huaqi_src/layers/capabilities/personality/engine.py`
- Modify: `huaqi_src/layers/capabilities/personality/updater.py`
- Modify: `huaqi_src/layers/data/profile/narrative.py`
- Modify: `huaqi_src/layers/data/profile/manager.py`
- Modify: `huaqi_src/layers/data/memory/search/llm_search.py`
- Modify: `huaqi_src/cli/chat.py`
- Modify: `huaqi_src/agent/nodes/chat_nodes.py`
- Create: `tests/unit/layers/test_misc_prompts.py`

### Step 1: 写失败测试

```python
# tests/unit/layers/test_misc_prompts.py

def test_world_news_uses_loader(self, tmp_path):
    """AC-27"""

def test_learning_uses_loader(self, tmp_path):
    """AC-28"""

def test_profile_uses_loader(self, tmp_path):
    """AC-29"""

def test_personality_uses_loader(self, tmp_path):
    """AC-30"""

def test_memory_search_uses_loader(self, tmp_path):
    """AC-31"""

def test_cli_chat_uses_loader(self, tmp_path):
    """AC-32"""

def test_chat_agent_uses_loader(self, tmp_path):
    """AC-23"""

def test_onboarding_uses_loader(self, tmp_path):
    """AC-34"""
```

### Step 2: 运行确认失败

### Step 3: 写实现

逐一替换每个模块中的硬编码 prompt：
- 内联字符串 → `loader.load(scene_id, **variables)`
- 保持原有的 `.format()` 变量注入逻辑不变，作为模板变量传入 loader
- `PersonalityEngine.to_prompt()` 特殊处理：该方法本质是根据字段值**动态生成** prompt，不适合完全外置。改为从 base.md 加载角色部分，动态部分保留在代码中

### Step 4: 运行确认通过

### Step 5: 更新验收测试

---

## Task 7: CLI 命令 + INDEX.md 自动生成

**Files:**
- Modify: `huaqi_src/cli/__init__.py`
- Create: `huaqi_src/cli/commands/prompts.py`

### Step 1: 写失败测试

```python
# 在 smoke_test.py 或 unit test 中

def test_cli_prompts_list(self):
    """AC-13: huaqi prompts list 命令可执行"""

def test_cli_prompts_list_includes_base(self):
    """AC-14: 输出包含 base.md 条目"""

def test_index_file_exists(self, tmp_path):
    """AC-11: INDEX.md 存在"""

def test_index_describes_effect(self, tmp_path):
    """AC-12: INDEX.md 包含'影响的功能'和'修改效果'"""

def test_index_auto_updates(self, tmp_path):
    """AC-15: 新增文件后 INDEX.md 自动更新"""
```

### Step 2: 运行确认失败

### Step 3: 写实现

CLI 命令:
```python
# huaqi_src/cli/commands/prompts.py

@app.command(name="list")
def prompts_list():
    """列出所有提示词及其功能描述"""
    loader = get_prompt_loader()
    prompts_dir = loader._prompts_dir
    index_path = prompts_dir / "INDEX.md"
    
    if not index_path.exists():
        console.print("[red]INDEX.md 不存在，请先运行 huaqi 初始化[/red]")
        return
    
    # 解析 INDEX.md 并格式化输出表格
    ...
```

INDEX.md 自动生成逻辑实现在 `PromptInitializer.rebuild_index()` 中。

### Step 4: 运行确认通过

### Step 5: 更新验收测试

---

## Task 8: 清理硬编码 + 全局回归

**Files:**
- Modify: 上述所有源文件（去除硬编码残留）
- Modify: `tests/smoke_test.py`（追加 `TestPromptsOverhaul` 类）

### Step 1: 写回归测试

```python
# tests/smoke_test.py 末尾

class TestPromptsOverhaul:
    """提示词体系重构功能验收。
    Spec: docs/specs/prompts-overhaul.md
    """

    def test_all_scene_ids_have_files(self, data_dir, set_data_dir):
        """所有 scene ID 都有对应的 .md 文件."""

    def test_prompts_match_original(self, data_dir, set_data_dir):
        """AC-37: 迁移后 prompt 语义与原有硬编码一致."""
        # 逐一比对每个 scene 的内置默认值和当前硬编码值

    def test_no_hardcoded_prompts(self):
        """AC-38: 无硬编码 prompt 残留在 .py 文件中."""

    def test_concurrent_loads_safe(self, tmp_path):
        """AC-39: 并发加载无竞态条件."""

    def test_empty_file_graceful(self, tmp_path):
        """AC-40: 空文件降级为内置默认值."""

    def test_missing_base_graceful(self, tmp_path):
        """AC-41: base.md 被删除后仍能正常工作."""
```

### Step 2: 运行确认失败（测试检测到硬编码残留）

```bash
pytest tests/smoke_test.py::TestPromptsOverhaul -v
```

### Step 3: 完成清理

- 去除所有 `.py` 文件中残留的硬编码 prompt 字符串
- 确保每个 LLM 调用点都通过 `PromptLoader` 获取 prompt
- `PersonalityEngine.to_prompt()` 保留动态生成逻辑（该函数本质是数据→prompt 转换，不是静态 prompt）

### Step 4: 运行全部测试确认通过

```bash
pytest tests/smoke_test.py -v     # 全部 pass
pytest tests/unit/ -x             # 全部 pass
pytest tests/ -x --tb=short       # 全部 pass（不含 e2e）
```

---

## 实施顺序依赖

```
Task 1 (PromptLoader 核心)
  ↓
Task 2 (Initializer + base.md)
  ↓
Task 3 (scheduler)  ← 独立，可与 Task 4-6 并行
  ↓
Task 4 (reports)    ← 独立
  ↓
Task 5 (TELOS)      ← 独立
  ↓
Task 6 (其余模块)   ← 独立
  ↓
Task 7 (CLI + INDEX) ← 依赖 Task 2
  ↓
Task 8 (清理回归)    ← 依赖所有 Task
```

Task 3-6 均依赖 Task 1-2，但彼此之间独立，可任意顺序执行。
