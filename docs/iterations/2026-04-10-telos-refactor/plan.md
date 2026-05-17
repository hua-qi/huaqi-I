# Telos 系统重构实现计划

**Goal:** 修复 Telos 系统的四个核心问题：接入 Agent 上下文注入、自动提炼触发、流水线性能优化（Step3/4/5合并+并行）、People 维度独立化。

**Architecture:** 优先级从高到低：(1) Agent 注入接入（立竿见影）→ (2) 自动提炼触发（信号能流动）→ (3) 流水线合并并行（性能提升）→ (4) 置信度重构（质量提升）→ (5) People 独立化 → (6) 定时复审 → (7) 冷启动问卷升级。每个 Task 都是独立可测、可提交的单元。

**Tech Stack:** Python 3.9+, Pydantic v2, LangGraph, pytest, asyncio, APScheduler

---

## 阅读顺序（先读这些，再动手）

在开始任何 Task 之前，建议先通读以下文件：

| 文件 | 为什么读 |
|------|--------|
| `huaqi_src/agent/nodes/chat_nodes.py` | 了解 `build_context` 现状和注入点 |
| `huaqi_src/agent/state.py` | 了解 `AgentState` 字段（`telos_snapshot` 已在里面） |
| `huaqi_src/layers/growth/telos/context.py` | 了解 `TelosContextBuilder` 已实现的接口 |
| `huaqi_src/layers/growth/telos/engine.py` | 了解 Step1/3/4/5 的 prompt 和 Output 数据结构 |
| `huaqi_src/layers/data/raw_signal/pipeline.py` | 了解 `DistillationPipeline.process()` 的逻辑 |
| `huaqi_src/scheduler/apscheduler_adapter.py` | 了解定时任务注册接口 |
| `huaqi_src/layers/growth/telos/models.py` | 了解 `STANDARD_DIMENSIONS`、`TelosDimension.to_markdown()` |
| `tests/integration/test_telos_to_agent.py` | 了解现有集成测试期望的行为 |
| `tests/integration/test_cold_start.py` | 了解冷启动问卷的测试结构 |

**运行测试的命令：**
```bash
pytest tests/ -v
pytest tests/unit/layers/growth/ -v
pytest tests/integration/ -v
```

---

## Task 1：接入 Agent 上下文注入（最高优先级）

**背景：** `TelosContextBuilder` 已在 `context.py` 实现，`AgentState` 的 `telos_snapshot` 字段已定义，但 `chat_nodes.py` 的 `build_context()` 函数完全没有调用它。这是最低成本、最高价值的改动。

**新设计：** 读取各维度文件的 `frontmatter + ## 当前认知`，跳过 `## 更新历史`，每维度约5~10行，共50~80行。不使用 INDEX.md（太简短）。

**Files:**
- Modify: `huaqi_src/layers/growth/telos/manager.py`（新增 `get_dimension_snippet` 方法）
- Modify: `huaqi_src/layers/growth/telos/context.py`（修改 `build_telos_snapshot` 读取方式）
- Modify: `huaqi_src/agent/nodes/chat_nodes.py`（在 `build_context` 中接入）
- Test: `tests/integration/test_telos_to_agent.py`（现有测试）
- Test: `tests/unit/agent/test_chat_nodes.py`（新增测试）

---

### Task 1.1：TelosManager 新增维度片段读取方法

**Step 1: 写失败测试**

在 `tests/unit/layers/growth/test_telos_manager.py` 末尾追加：

```python
class TestTelosManagerGetDimensionSnippet:
    def test_get_snippet_contains_frontmatter_and_content(self, telos_dir, telos_manager):
        snippet = telos_manager.get_dimension_snippet("beliefs")
        assert "beliefs" in snippet
        assert "## 当前认知" in snippet

    def test_get_snippet_excludes_history(self, telos_dir, telos_manager):
        from datetime import datetime, timezone
        from huaqi_src.layers.growth.telos.models import HistoryEntry
        entry = HistoryEntry(
            version=1,
            change="测试变化",
            trigger="测试触发",
            confidence=0.7,
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        telos_manager.update("beliefs", "新内容", entry, 0.7)
        snippet = telos_manager.get_dimension_snippet("beliefs")
        assert "## 更新历史" not in snippet

    def test_get_all_snippets_returns_dict(self, telos_manager):
        snippets = telos_manager.get_all_dimension_snippets()
        assert isinstance(snippets, dict)
        assert "beliefs" in snippets
        assert "goals" in snippets
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/unit/layers/growth/test_telos_manager.py::TestTelosManagerGetDimensionSnippet -v
```
预期：`FAILED AttributeError: 'TelosManager' object has no attribute 'get_dimension_snippet'`

**Step 3: 实现方法**

在 `huaqi_src/layers/growth/telos/manager.py` 的 `TelosManager` 类末尾追加（在 `_rebuild_index` 之前）：

```python
def get_dimension_snippet(self, name: str) -> str:
    p = self._path(name)
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    separator_index = text.find("\n---\n\n## 更新历史")
    if separator_index != -1:
        return text[:separator_index].strip()
    return text.strip()

def get_all_dimension_snippets(self) -> dict[str, str]:
    result = {}
    for dim in self.list_active():
        result[dim.name] = self.get_dimension_snippet(dim.name)
    return result
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/unit/layers/growth/test_telos_manager.py::TestTelosManagerGetDimensionSnippet -v
```
预期：PASSED

**Step 5: 提交**

```bash
git add huaqi_src/layers/growth/telos/manager.py tests/unit/layers/growth/test_telos_manager.py
git commit -m "feat(telos): add get_dimension_snippet to TelosManager"
```

---

### Task 1.2：修改 TelosContextBuilder.build_telos_snapshot

**背景：** 当前 `build_telos_snapshot` 读取 INDEX.md，每维度只取前30字，太简短。新方案读取各维度文件的 `frontmatter + ## 当前认知`，跳过 `## 更新历史`。

**Step 1: 写失败测试**

在 `tests/integration/test_telos_to_agent.py` 的 `TestTelosContextBuilder` 类末尾追加：

```python
def test_build_telos_snapshot_contains_full_content(self, telos_manager):
    from datetime import datetime, timezone
    from huaqi_src.layers.growth.telos.models import HistoryEntry
    entry = HistoryEntry(
        version=1,
        change="信念改变了",
        trigger="信号触发",
        confidence=0.8,
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    telos_manager.update(
        "beliefs",
        "选择比努力更重要，专注在少数关键事情上。",
        entry,
        0.8,
    )
    builder = TelosContextBuilder(telos_manager=telos_manager)
    snapshot = builder.build_telos_snapshot()
    assert "选择比努力更重要" in snapshot

def test_build_telos_snapshot_excludes_history(self, telos_manager):
    from datetime import datetime, timezone
    from huaqi_src.layers.growth.telos.models import HistoryEntry
    entry = HistoryEntry(
        version=1,
        change="不应该出现在快照中的历史内容",
        trigger="触发",
        confidence=0.5,
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    telos_manager.update("beliefs", "当前认知内容", entry, 0.5)
    builder = TelosContextBuilder(telos_manager=telos_manager)
    snapshot = builder.build_telos_snapshot()
    assert "不应该出现在快照中的历史内容" not in snapshot
```

**Step 2: 运行测试确认失败（或部分失败）**

```bash
pytest tests/integration/test_telos_to_agent.py::TestTelosContextBuilder -v
```

**Step 3: 修改 build_telos_snapshot 方法**

打开 `huaqi_src/layers/growth/telos/context.py`，将 `build_telos_snapshot` 方法替换为：

```python
def build_telos_snapshot(self) -> str:
    snippets = self._mgr.get_all_dimension_snippets()
    if not snippets:
        return ""
    parts = ["## 核心认知（TELOS）", ""]
    for name, snippet in snippets.items():
        if snippet:
            parts.append(snippet)
            parts.append("")
    return "\n".join(parts).strip()
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/integration/test_telos_to_agent.py::TestTelosContextBuilder -v
```
预期：PASSED

**Step 5: 提交**

```bash
git add huaqi_src/layers/growth/telos/context.py tests/integration/test_telos_to_agent.py
git commit -m "feat(telos): build_telos_snapshot reads dimension files instead of INDEX.md"
```

---

### Task 1.3：在 build_context 中接入 TelosContextBuilder

**Step 1: 写失败测试**

在 `tests/unit/agent/test_chat_nodes.py` 末尾追加：

```python
class TestBuildContextWithTelos:
    def test_build_context_injects_telos_snapshot(self, tmp_path):
        from huaqi_src.agent.state import create_initial_state
        from huaqi_src.agent.nodes.chat_nodes import build_context
        from huaqi_src.config import paths as config_paths
        from huaqi_src.layers.growth.telos.manager import TelosManager
        from unittest.mock import patch
        from datetime import datetime, timezone
        from huaqi_src.layers.growth.telos.models import HistoryEntry

        config_paths._USER_DATA_DIR = tmp_path
        telos_dir = tmp_path / "telos"
        telos_dir.mkdir()
        mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
        mgr.init()
        entry = HistoryEntry(
            version=1, change="测试", trigger="测试",
            confidence=0.8, updated_at=datetime.now(timezone.utc)
        )
        mgr.update("beliefs", "选择比努力更重要", entry, 0.8)

        state = create_initial_state()
        with patch("huaqi_src.agent.nodes.chat_nodes._get_telos_manager", return_value=mgr):
            result = build_context(state)

        system_prompt = result["workflow_data"]["system_prompt"]
        assert "选择比努力更重要" in system_prompt

    def test_build_context_falls_back_gracefully_when_no_telos(self, tmp_path):
        from huaqi_src.agent.state import create_initial_state
        from huaqi_src.agent.nodes.chat_nodes import build_context
        from huaqi_src.config import paths as config_paths

        config_paths._USER_DATA_DIR = tmp_path
        state = create_initial_state()
        result = build_context(state)
        assert "system_prompt" in result["workflow_data"]
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/unit/agent/test_chat_nodes.py::TestBuildContextWithTelos -v
```
预期：`FAILED` (没有 `_get_telos_manager` 函数)

**Step 3: 修改 chat_nodes.py**

在 `huaqi_src/agent/nodes/chat_nodes.py` 的 import 区域末尾追加：

```python
from huaqi_src.layers.growth.telos.context import TelosContextBuilder
```

在 `build_context` 函数**之前**，新增辅助函数：

```python
def _get_telos_manager():
    try:
        from huaqi_src.config.paths import get_telos_dir
        from huaqi_src.layers.growth.telos.manager import TelosManager
        telos_dir = get_telos_dir()
        if not telos_dir.exists():
            return None
        return TelosManager(telos_dir=telos_dir, git_commit=False)
    except Exception:
        return None
```

将 `build_context` 函数替换为：

```python
def build_context(state: AgentState) -> Dict[str, Any]:
    personality_context = state.get("personality_context", "")

    user_profile_context = ""
    try:
        profile_manager = get_profile_manager()
        user_profile_context = profile_manager.get_system_prompt_addition()
    except Exception:
        pass

    telos_snapshot = ""
    try:
        telos_mgr = _get_telos_manager()
        if telos_mgr is not None:
            builder = TelosContextBuilder(telos_manager=telos_mgr)
            telos_snapshot = builder.build_telos_snapshot()
    except Exception:
        pass

    system_prompt = build_system_prompt(
        personality_context,
        user_profile_context,
        telos_snapshot,
    )

    workflow_data = state.get("workflow_data", {})
    workflow_data["system_prompt"] = system_prompt

    return {"workflow_data": workflow_data}
```

将 `build_system_prompt` 函数签名和函数体替换为：

```python
def build_system_prompt(
    personality_context: Optional[str] = None,
    user_profile_context: Optional[str] = None,
    telos_snapshot: Optional[str] = None,
) -> str:
    base_prompt = """你是 Huaqi (花旗)，一个个人 AI 伴侣系统。

你的职责：
1. 作为用户的数字伙伴，提供陪伴和支持
2. 记住用户的重要信息和偏好
3. 帮助用户记录日记、追踪成长、管理目标
4. 在内容创作时提供协助
5. 当用户询问新闻、时事、世界动态时，必须先调用 search_worldnews_tool 查询本地数据；如果工具返回"本地未找到"或无结果，必须紧接着调用 google_search_tool 在互联网上搜索，不得直接回答

回复风格：
- 温暖、真诚、有同理心
- 简洁明了，避免冗长
- 适当使用 emoji 增加亲和力
- 记住用户的上下文，保持对话连贯
- 根据用户的情绪状态调整回应方式
- 关注用户的深层需求，不只是表面问题
"""

    if personality_context:
        base_prompt += f"\n\n{personality_context}\n"

    if user_profile_context:
        base_prompt += f"\n{user_profile_context}\n"

    if telos_snapshot:
        base_prompt += f"\n\n## 你对这个用户的了解\n\n{telos_snapshot}\n"

    return base_prompt
```

**Step 4: 检查 get_telos_dir 是否存在**

```bash
grep -r "get_telos_dir" huaqi_src/config/
```

如果不存在，在 `huaqi_src/config/paths.py` 末尾追加：
```python
def get_telos_dir() -> Path:
    return get_user_data_dir() / "telos"
```

**Step 5: 运行测试确认通过**

```bash
pytest tests/unit/agent/test_chat_nodes.py::TestBuildContextWithTelos -v
pytest tests/integration/test_telos_to_agent.py -v
```
预期：PASSED

**Step 6: 提交**

```bash
git add huaqi_src/agent/nodes/chat_nodes.py huaqi_src/config/paths.py tests/unit/agent/test_chat_nodes.py
git commit -m "feat(agent): inject Telos snapshot into build_context system prompt"
```

---

## Task 2：自动提炼触发（DistillationJob）

**背景：** `DistillationPipeline.process()` 已实现，但没有定时任务去捞取未处理的 RawSignal 并批量触发它。信号存进去就永远躺在数据库。需要新增一个 `DistillationJob` 注册到 scheduler。

**Files:**
- Create: `huaqi_src/scheduler/distillation_job.py`
- Modify: `huaqi_src/scheduler/jobs.py`（注册新 job）
- Test: `tests/unit/scheduler/test_growth_jobs.py`（追加测试）

---

### Task 2.1：创建 DistillationJob

**Step 1: 写失败测试**

打开 `tests/unit/scheduler/test_growth_jobs.py`，追加：

```python
class TestDistillationJob:
    def test_run_processes_unprocessed_signals(self, tmp_path):
        from huaqi_src.scheduler.distillation_job import run_distillation_job
        from unittest.mock import MagicMock, patch

        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = {"signal_id": "s1", "pipeline_runs": []}

        mock_store = MagicMock()
        from datetime import datetime, timezone
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
        fake_signal = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="测试信号内容",
        )
        mock_store.query.return_value = [fake_signal]

        with patch("huaqi_src.scheduler.distillation_job._get_pipeline", return_value=mock_pipeline):
            with patch("huaqi_src.scheduler.distillation_job._get_signal_store", return_value=mock_store):
                result = run_distillation_job(limit=10)

        assert result["processed"] == 1
        mock_pipeline.process.assert_called_once_with(fake_signal)

    def test_run_returns_zero_when_no_unprocessed(self, tmp_path):
        from huaqi_src.scheduler.distillation_job import run_distillation_job
        from unittest.mock import MagicMock, patch

        mock_pipeline = MagicMock()
        mock_store = MagicMock()
        mock_store.query.return_value = []

        with patch("huaqi_src.scheduler.distillation_job._get_pipeline", return_value=mock_pipeline):
            with patch("huaqi_src.scheduler.distillation_job._get_signal_store", return_value=mock_store):
                result = run_distillation_job(limit=10)

        assert result["processed"] == 0
        mock_pipeline.process.assert_not_called()
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/unit/scheduler/test_growth_jobs.py::TestDistillationJob -v
```
预期：`FAILED ModuleNotFoundError: No module named 'huaqi_src.scheduler.distillation_job'`

**Step 3: 创建 distillation_job.py**

创建 `huaqi_src/scheduler/distillation_job.py`：

```python
from typing import Any, Dict

from huaqi_src.layers.data.raw_signal.models import RawSignalFilter


def _get_signal_store():
    from huaqi_src.config.paths import get_db_path
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    adapter = SQLiteStorageAdapter(db_path=get_db_path())
    return RawSignalStore(adapter=adapter)


def _get_pipeline():
    from huaqi_src.config.paths import get_telos_dir, get_db_path
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
    from huaqi_src.layers.growth.telos.engine import TelosEngine
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.growth_events import GrowthEventStore

    adapter = SQLiteStorageAdapter(db_path=get_db_path())
    signal_store = RawSignalStore(adapter=adapter)
    event_store = GrowthEventStore(adapter=adapter)

    telos_dir = get_telos_dir()
    telos_mgr = TelosManager(telos_dir=telos_dir, git_commit=True)

    from huaqi_src.cli.context import build_llm_manager
    llm_mgr = build_llm_manager(temperature=0.3, max_tokens=2000)
    if llm_mgr is None:
        raise RuntimeError("未配置 LLM，无法运行提炼任务")

    active_name = llm_mgr.get_active_provider()
    cfg = llm_mgr._configs[active_name]
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.api_base or None,
        temperature=0.3,
        max_tokens=2000,
    )

    engine = TelosEngine(telos_manager=telos_mgr, llm=llm)
    return DistillationPipeline(
        signal_store=signal_store,
        event_store=event_store,
        telos_manager=telos_mgr,
        engine=engine,
    )


def run_distillation_job(
    user_id: str = "default",
    limit: int = 10,
) -> Dict[str, Any]:
    signal_store = _get_signal_store()
    unprocessed = signal_store.query(
        RawSignalFilter(user_id=user_id, processed=0, limit=limit)
    )

    if not unprocessed:
        return {"processed": 0, "errors": 0}

    pipeline = _get_pipeline()
    processed = 0
    errors = 0

    for signal in unprocessed:
        try:
            pipeline.process(signal)
            processed += 1
        except Exception as e:
            errors += 1
            import logging
            logging.getLogger(__name__).error(f"提炼失败 signal={signal.id}: {e}")

    return {"processed": processed, "errors": errors}
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/unit/scheduler/test_growth_jobs.py::TestDistillationJob -v
```
预期：PASSED

**Step 5: 提交**

```bash
git add huaqi_src/scheduler/distillation_job.py tests/unit/scheduler/test_growth_jobs.py
git commit -m "feat(scheduler): add DistillationJob for automatic signal processing"
```

---

### Task 2.2：注册 DistillationJob 到 Scheduler

**Step 1: 阅读现有的 jobs.py**

```bash
cat huaqi_src/scheduler/jobs.py
```

了解如何注册其他 job，然后参考该模式添加。

**Step 2: 在 jobs.py 末尾追加注册函数**

定位 `huaqi_src/scheduler/jobs.py`，在末尾追加：

```python
def register_distillation_job(
    scheduler_adapter,
    interval_seconds: int = 3600,
    user_id: str = "default",
    limit: int = 10,
) -> None:
    from huaqi_src.scheduler.distillation_job import run_distillation_job

    def _job():
        run_distillation_job(user_id=user_id, limit=limit)

    scheduler_adapter.add_interval_job(
        func=_job,
        seconds=interval_seconds,
        job_id="distillation_job",
    )
```

**Step 3: 运行全量测试确认无回归**

```bash
pytest tests/unit/scheduler/ -v
```
预期：全部 PASSED

**Step 4: 提交**

```bash
git add huaqi_src/scheduler/jobs.py
git commit -m "feat(scheduler): register DistillationJob in scheduler"
```

---

## Task 3：Step3/4/5 合并为单次 LLM 调用（性能优化）

**背景：** 现在每个维度需要 Step3(1次) + Step4(1次) + Step5(1次) = 3次串行 LLM 调用。合并后 1 个维度只需 1次，多维度并行后总时间约等于 Step1(1次) + 最慢维度(1次) = 2次。

**新输出结构（`CombinedStepOutput`）：**
```json
{
  "should_update": true,
  "new_content": "...",
  "consistency_score": 0.8,
  "history_entry": {"change": "...", "trigger": "..."},
  "is_growth_event": true,
  "growth_title": "...",
  "growth_narrative": "..."
}
```

**置信度新公式：**
```python
confidence = count_score * 0.4 + consistency_score * 0.6
count_score = min(recent_signal_count / 10, 1.0)
```

**Files:**
- Modify: `huaqi_src/layers/growth/telos/engine.py`（新增 `CombinedStepOutput` 和 `step345_combined` 方法）
- Modify: `huaqi_src/layers/data/raw_signal/pipeline.py`（调用新方法，支持并行）
- Test: `tests/unit/layers/growth/test_telos_engine.py`（追加测试）
- Test: `tests/integration/test_raw_signal_to_telos.py`（追加测试）

---

### Task 3.1：新增 CombinedStepOutput 和 step345_combined

**Step 1: 写失败测试**

在 `tests/unit/layers/growth/test_telos_engine.py` 末尾追加：

```python
@pytest.fixture
def mock_combined_step() -> dict:
    return {
        "should_update": True,
        "new_content": "当前最大挑战是目标感缺失，选择方向比埋头努力更重要。",
        "consistency_score": 0.8,
        "history_entry": {
            "change": "从「缺乏专注」更新为「目标感缺失」",
            "trigger": "日记连续 3 次提到方向感问题",
        },
        "is_growth_event": True,
        "growth_title": "开始质疑努力的方向",
        "growth_narrative": "你开始意识到方向比努力更重要了。",
    }


class TestCombinedStepOutput:
    def test_valid_combined_output(self, mock_combined_step):
        from huaqi_src.layers.growth.telos.engine import CombinedStepOutput
        out = CombinedStepOutput(**mock_combined_step)
        assert out.should_update is True
        assert out.consistency_score == 0.8
        assert out.is_growth_event is True

    def test_combined_output_no_update(self):
        from huaqi_src.layers.growth.telos.engine import CombinedStepOutput
        out = CombinedStepOutput(
            should_update=False,
            new_content=None,
            consistency_score=0.2,
            history_entry=None,
            is_growth_event=False,
            growth_title=None,
            growth_narrative=None,
        )
        assert out.should_update is False


class TestStep345Combined:
    def test_step345_single_llm_call(self, telos_manager, mock_combined_step):
        import json
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(mock_combined_step))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = engine.step345_combined(
            dimension="challenges",
            signal_summaries=["摘要1", "摘要2", "摘要3"],
            days=30,
            recent_signal_count=5,
        )

        assert mock_llm.invoke.call_count == 1
        assert result.should_update is True
        assert result.is_growth_event is True

    def test_step345_calculates_confidence_correctly(self, telos_manager, mock_combined_step):
        import json
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(mock_combined_step))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = engine.step345_combined(
            dimension="challenges",
            signal_summaries=["摘要"],
            days=30,
            recent_signal_count=5,
        )

        expected_count_score = min(5 / 10, 1.0)
        expected_confidence = expected_count_score * 0.4 + 0.8 * 0.6
        assert abs(result.confidence - expected_confidence) < 0.001

    def test_step345_updates_manager_when_should_update(self, telos_manager, mock_combined_step):
        import json
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(mock_combined_step))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        engine.step345_combined(
            dimension="challenges",
            signal_summaries=["摘要"],
            days=30,
            recent_signal_count=3,
        )

        dim = telos_manager.get("challenges")
        assert dim.update_count == 1
        assert "目标感缺失" in dim.content
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/unit/layers/growth/test_telos_engine.py::TestCombinedStepOutput -v
pytest tests/unit/layers/growth/test_telos_engine.py::TestStep345Combined -v
```
预期：`FAILED ImportError: cannot import name 'CombinedStepOutput'`

**Step 3: 在 engine.py 中新增合并步骤**

在 `huaqi_src/layers/growth/telos/engine.py` 的 `Step5Output` 类定义之后，追加新的类：

```python
class CombinedStepOutput(BaseModel):
    should_update: bool
    new_content: Optional[str]
    consistency_score: float
    history_entry: Optional[Dict[str, str]]
    is_growth_event: bool
    growth_title: Optional[str]
    growth_narrative: Optional[str]
    confidence: float = 0.0
```

在 `engine.py` 中，在现有 Prompt 常量之后，追加新的合并 Prompt：

```python
_STEP345_COMBINED_PROMPT = """\
你是用户的个人成长分析师兼见证者。
请同时完成三件事：
1. 判断是否应更新「{dimension}」维度的认知
2. 如果更新，生成新的认知内容和历史记录
3. 判断这次变化是否是值得记录的成长事件

以下是当前对这个用户的了解：
{telos_index}

以下是最近 {days} 天，关于「{dimension}」维度的 {count} 条信号摘要：
{signal_summaries}

当前该维度的认知是：
{current_content}

判断标准（成长事件）：
- 核心层维度变化 → 几乎总是值得
- 中间层维度的方向性转变 → 值得
- 表面层的日常积累 → 通常不值得

consistency_score 的含义：这些信号指向同一个方向的程度（0.0=完全矛盾，1.0=高度一致）

输出合法 JSON，不要有任何额外文字：
{{
  "should_update": true/false,
  "new_content": "...",
  "consistency_score": 0.0-1.0,
  "history_entry": {{
    "change": "...",
    "trigger": "..."
  }},
  "is_growth_event": true/false,
  "growth_title": "...",
  "growth_narrative": "..."
}}\
"""
```

在 `TelosEngine` 类末尾追加 `step345_combined` 方法（放在 `run_pipeline` 之前）：

```python
def step345_combined(
    self,
    dimension: str,
    signal_summaries: List[str],
    days: int,
    recent_signal_count: int,
) -> CombinedStepOutput:
    dim = self._mgr.get(dimension)
    prompt = _STEP345_COMBINED_PROMPT.format(
        telos_index=self._telos_index(),
        days=days,
        dimension=dimension,
        count=len(signal_summaries),
        signal_summaries="\n".join(f"- {s}" for s in signal_summaries),
        current_content=dim.content,
    )
    response = self._llm.invoke(prompt)
    data = _parse_json(response.content)
    result = CombinedStepOutput(**data)

    count_score = min(recent_signal_count / 10, 1.0)
    consistency_score = result.consistency_score
    result.confidence = count_score * 0.4 + consistency_score * 0.6

    if result.should_update and result.new_content and result.history_entry:
        version = dim.update_count + 1
        entry = HistoryEntry(
            version=version,
            change=result.history_entry["change"],
            trigger=result.history_entry["trigger"],
            confidence=result.confidence,
            updated_at=datetime.now(timezone.utc),
        )
        self._mgr.update(
            name=dimension,
            new_content=result.new_content,
            history_entry=entry,
            confidence=result.confidence,
        )

    return result
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/unit/layers/growth/test_telos_engine.py::TestCombinedStepOutput -v
pytest tests/unit/layers/growth/test_telos_engine.py::TestStep345Combined -v
```
预期：PASSED

**Step 5: 提交**

```bash
git add huaqi_src/layers/growth/telos/engine.py tests/unit/layers/growth/test_telos_engine.py
git commit -m "feat(telos): add CombinedStepOutput and step345_combined for merged pipeline"
```

---

### Task 3.2：DistillationPipeline 使用新方法并行处理多维度

**Step 1: 写失败测试**

在 `tests/unit/layers/data/test_raw_signal_pipeline.py` 末尾追加：

```python
class TestDistillationPipelineCombinedStep:
    def test_pipeline_uses_step345_combined_not_separate(self, signal_store, event_store, telos_manager):
        import json
        from unittest.mock import MagicMock, patch
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
        from huaqi_src.layers.growth.telos.engine import TelosEngine, Step1Output, CombinedStepOutput
        from datetime import datetime, timezone

        mock_llm = MagicMock()
        step1_data = {
            "dimensions": ["challenges", "goals"],
            "emotion": "negative",
            "intensity": 0.8,
            "signal_strength": "strong",
            "strong_reason": "强信号",
            "summary": "测试",
            "new_dimension_hint": None,
        }
        combined_data = {
            "should_update": True,
            "new_content": "新内容",
            "consistency_score": 0.8,
            "history_entry": {"change": "变化", "trigger": "触发"},
            "is_growth_event": False,
            "growth_title": None,
            "growth_narrative": None,
        }
        mock_llm.invoke.side_effect = [
            MagicMock(content=json.dumps(step1_data)),
            MagicMock(content=json.dumps(combined_data)),
            MagicMock(content=json.dumps(combined_data)),
        ]
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
        pipeline = DistillationPipeline(
            signal_store=signal_store,
            event_store=event_store,
            telos_manager=telos_manager,
            engine=engine,
        )
        signal = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="测试信号",
        )
        result = pipeline.process(signal)
        assert result["signal_id"] == signal.id
        assert len(result["pipeline_runs"]) > 0
```

**Step 2: 运行测试**

```bash
pytest tests/unit/layers/data/test_raw_signal_pipeline.py::TestDistillationPipelineCombinedStep -v
```

如果通过，不需要修改 pipeline.py，直接跳到 Step 5 提交。
如果失败，检查是否需要更新 `pipeline.py` 中对 `run_pipeline` 的调用。

**Step 3（条件执行）: 更新 DistillationPipeline 使用新方法**

如果 `pipeline.py` 仍调用旧的 `run_pipeline`，将其中的维度处理循环替换为调用 `step345_combined`：

在 `DistillationPipeline.process` 中，将原有的：
```python
run_result = self._engine.run_pipeline(...)
```

替换为（为每个维度调用合并方法，并计算 recent_signal_count）：
```python
since = datetime.now(timezone.utc) - timedelta(days=self._days_window)
recent_count = self._signal_store.count(
    RawSignalFilter(user_id=signal.user_id, processed=1, since=since)
)
combined_result = self._engine.step345_combined(
    dimension=dimension,
    signal_summaries=summaries,
    days=self._days_window,
    recent_signal_count=recent_count,
)
run_result = {
    "updated": combined_result.should_update,
    "growth_event": combined_result if combined_result.is_growth_event else None,
}
```

并修改成长事件构建逻辑：
```python
if combined_result.should_update and combined_result.is_growth_event:
    dim = self._mgr.get(dimension)
    event = GrowthEvent(
        user_id=signal.user_id,
        dimension=dimension,
        layer=layer.value if layer else "surface",
        title=combined_result.growth_title or "",
        narrative=combined_result.growth_narrative or "",
        new_content=dim.content,
        trigger_signals=[signal.id],
        occurred_at=signal.timestamp,
    )
    self._event_store.save(event)
```

**Step 4: 运行全量测试确认无回归**

```bash
pytest tests/unit/layers/data/ -v
pytest tests/integration/test_raw_signal_to_telos.py -v
```
预期：PASSED

**Step 5: 提交**

```bash
git add huaqi_src/layers/data/raw_signal/pipeline.py tests/unit/layers/data/test_raw_signal_pipeline.py
git commit -m "feat(pipeline): use step345_combined in DistillationPipeline"
```

---

## Task 4：People 维度从标准维度中独立（models.py 修改）

**背景：** `people` 的存储结构（多 Person 对象）与其他维度（一段认知文字）完全不同，强行放在同一框架内会导致 `TelosEngine` 错误地对它进行语义提炼。需要从 `STANDARD_DIMENSIONS` 中移除，并更新相关常量。

**注意：** `PersonExtractor` 和 `PeopleGraph` 已经存在，这里只需要从维度列表中解耦，并在 `DistillationPipeline.process` 的 Step1 分叉后调用 `PersonExtractor`。

**Files:**
- Modify: `huaqi_src/layers/growth/telos/models.py`（从 STANDARD_DIMENSIONS 移除 people）
- Modify: `huaqi_src/layers/data/raw_signal/pipeline.py`（Step1 后分叉调用 PersonExtractor）
- Test: `tests/unit/layers/growth/test_telos_models.py`（追加测试）

---

### Task 4.1：从 STANDARD_DIMENSIONS 移除 people

**Step 1: 写失败测试**

在 `tests/unit/layers/growth/test_telos_models.py` 末尾追加：

```python
class TestStandardDimensionsNoPeople:
    def test_people_not_in_standard_dimensions(self):
        from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSIONS
        assert "people" not in STANDARD_DIMENSIONS

    def test_eight_standard_dimensions(self):
        from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSIONS
        assert len(STANDARD_DIMENSIONS) == 8

    def test_people_not_in_standard_dimension_layers(self):
        from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSION_LAYERS
        assert "people" not in STANDARD_DIMENSION_LAYERS
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/unit/layers/growth/test_telos_models.py::TestStandardDimensionsNoPeople -v
```
预期：`FAILED AssertionError: assert 'people' not in ['beliefs', 'models', ..., 'people', 'shadows']`

**Step 3: 修改 models.py**

在 `huaqi_src/layers/growth/telos/models.py` 中，将：
```python
STANDARD_DIMENSIONS = [
    "beliefs", "models", "narratives",
    "goals", "challenges", "strategies",
    "learned", "people", "shadows",
]
```
改为：
```python
STANDARD_DIMENSIONS = [
    "beliefs", "models", "narratives",
    "goals", "challenges", "strategies",
    "learned", "shadows",
]
```

同时移除 `STANDARD_DIMENSION_LAYERS` 中的 `people` 条目：
```python
# 删除这一行：
"people": DimensionLayer.SURFACE,
```

**Step 4: 同步修改 manager.py 中的初始内容字典**

在 `huaqi_src/layers/growth/telos/manager.py` 的 `_INITIAL_CONTENT` 字典中，删除 `"people": "（待补充）",` 这一行。

**Step 5: 运行全量测试，修复回归**

```bash
pytest tests/unit/layers/growth/ -v
```

任何因 `people` 维度被移除导致的测试失败，检查该测试是否测试了 people 作为标准维度的行为，将其更新为排除 people 或使用 People 子系统。

**Step 6: 运行完整测试套件**

```bash
pytest tests/ -v
```

**Step 7: 提交**

```bash
git add huaqi_src/layers/growth/telos/models.py huaqi_src/layers/growth/telos/manager.py tests/unit/layers/growth/test_telos_models.py
git commit -m "feat(telos): remove 'people' from STANDARD_DIMENSIONS, People is now independent"
```

---

### Task 4.2：在 DistillationPipeline 的 Step1 分叉后调用 PersonExtractor

**Step 1: 写失败测试**

在 `tests/unit/layers/data/test_raw_signal_pipeline.py` 末尾追加：

```python
class TestPeoplePipelineFork:
    def test_pipeline_calls_person_extractor_when_has_people(self, signal_store, event_store, telos_manager):
        import json
        from unittest.mock import MagicMock, patch
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
        from huaqi_src.layers.growth.telos.engine import TelosEngine
        from datetime import datetime, timezone

        mock_llm = MagicMock()
        step1_data = {
            "dimensions": ["goals"],
            "emotion": "positive",
            "intensity": 0.6,
            "signal_strength": "strong",
            "strong_reason": "强信号",
            "summary": "提到了老李",
            "new_dimension_hint": None,
            "has_people": True,
            "mentioned_names": ["老李"],
        }
        combined_data = {
            "should_update": False,
            "new_content": None,
            "consistency_score": 0.3,
            "history_entry": None,
            "is_growth_event": False,
            "growth_title": None,
            "growth_narrative": None,
        }
        mock_llm.invoke.side_effect = [
            MagicMock(content=json.dumps(step1_data)),
            MagicMock(content=json.dumps(combined_data)),
        ]
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        mock_extractor = MagicMock()
        mock_extractor.extract_from_text.return_value = []

        from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
        pipeline = DistillationPipeline(
            signal_store=signal_store,
            event_store=event_store,
            telos_manager=telos_manager,
            engine=engine,
            person_extractor=mock_extractor,
        )
        signal = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="今天和老李聊了很多",
        )
        pipeline.process(signal)
        mock_extractor.extract_from_text.assert_called_once_with(signal.content)
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/unit/layers/data/test_raw_signal_pipeline.py::TestPeoplePipelineFork -v
```

**Step 3: 修改 Step1Output 支持 has_people 和 mentioned_names**

在 `engine.py` 的 `Step1Output` 类中追加字段：
```python
class Step1Output(BaseModel):
    dimensions: List[str]
    emotion: str
    intensity: float
    signal_strength: SignalStrength
    strong_reason: Optional[str]
    summary: str
    new_dimension_hint: Optional[str]
    has_people: bool = False
    mentioned_names: List[str] = Field(default_factory=list)
```

同时更新 `_STEP1_PROMPT` 末尾的 JSON 格式，追加两个字段：
```
  "has_people": true/false,
  "mentioned_names": ["姓名1", "姓名2"]
```

**Step 4: 修改 DistillationPipeline 接受 person_extractor 并在 Step1 后调用**

在 `DistillationPipeline.__init__` 中追加参数：
```python
def __init__(
    self,
    signal_store: RawSignalStore,
    event_store: GrowthEventStore,
    telos_manager: TelosManager,
    engine: TelosEngine,
    signal_threshold: int = 3,
    days_window: int = 30,
    person_extractor=None,
) -> None:
    ...
    self._person_extractor = person_extractor
```

在 `process` 方法中，`self._signal_store.mark_processed(signal.id)` 之后，追加：
```python
if step1_result.has_people and self._person_extractor is not None:
    try:
        self._person_extractor.extract_from_text(signal.content)
    except Exception:
        pass
```

**Step 5: 运行测试确认通过**

```bash
pytest tests/unit/layers/data/test_raw_signal_pipeline.py::TestPeoplePipelineFork -v
```

**Step 6: 运行全量测试**

```bash
pytest tests/ -v
```

**Step 7: 提交**

```bash
git add huaqi_src/layers/growth/telos/engine.py huaqi_src/layers/data/raw_signal/pipeline.py tests/unit/layers/data/test_raw_signal_pipeline.py
git commit -m "feat(telos): People pipeline fork after Step1, person_extractor as optional dependency"
```

---

## Task 5：定时复审任务（超过 N 天无信号的维度）

**背景：** 维度内容可能已过时，但置信度不降。定时检查 `last_signal_at`（用维度文件的 `updated_at` 近似），超过阈值的维度触发轻量复审。

**Files:**
- Modify: `huaqi_src/layers/growth/telos/engine.py`（新增 `review_stale_dimension` 方法）
- Create: `huaqi_src/scheduler/review_job.py`
- Test: `tests/unit/layers/growth/test_telos_engine.py`（追加测试）
- Test: `tests/unit/scheduler/test_growth_jobs.py`（追加测试）

---

### Task 5.1：TelosEngine 新增 review_stale_dimension

**Step 1: 写失败测试**

在 `tests/unit/layers/growth/test_telos_engine.py` 末尾追加：

```python
@pytest.fixture
def mock_review_stale_update() -> dict:
    return {
        "is_stale": True,
        "new_consistency_score": 0.4,
        "reason": "超过30天无新信号，内容可能已过时",
    }

@pytest.fixture
def mock_review_stale_valid() -> dict:
    return {
        "is_stale": False,
        "new_consistency_score": 0.8,
        "reason": "内容依然准确",
    }


class TestReviewStaleDimension:
    def test_review_stale_returns_output(self, telos_manager, mock_review_stale_valid):
        import json
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(mock_review_stale_valid))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = engine.review_stale_dimension("beliefs", days_since_last_signal=40)

        assert result is not None
        assert hasattr(result, "is_stale")
        assert result.is_stale is False

    def test_review_stale_lowers_confidence_when_stale(self, telos_manager, mock_review_stale_update):
        import json
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(mock_review_stale_update))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        engine.review_stale_dimension("beliefs", days_since_last_signal=40)

        dim = telos_manager.get("beliefs")
        assert dim.confidence < 0.5
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/unit/layers/growth/test_telos_engine.py::TestReviewStaleDimension -v
```

**Step 3: 在 engine.py 中新增复审方法**

在 `engine.py` 中追加新的 Prompt 和类：

```python
_REVIEW_STALE_PROMPT = """\
你是用户的个人成长分析师。
该维度已超过 {days} 天没有收到新信号。
请判断当前认知是否可能已经过时。

维度：{dimension}
当前认知：
{current_content}

请判断：
1. 内容是否可能已过时？（考虑时间流逝、人的变化、情境变化）
2. 如果过时，置信度应该降低多少？（new_consistency_score 应在 0.0~0.6 之间）
3. 如果仍然有效，维持 consistency_score 不变

输出合法 JSON，不要有任何额外文字：
{{
  "is_stale": true/false,
  "new_consistency_score": 0.0-1.0,
  "reason": "..."
}}\
"""


class ReviewOutput(BaseModel):
    is_stale: bool
    new_consistency_score: float
    reason: str
```

在 `TelosEngine` 类中追加方法：

```python
def review_stale_dimension(
    self,
    dimension: str,
    days_since_last_signal: int,
) -> ReviewOutput:
    dim = self._mgr.get(dimension)
    prompt = _REVIEW_STALE_PROMPT.format(
        days=days_since_last_signal,
        dimension=dimension,
        current_content=dim.content,
    )
    response = self._llm.invoke(prompt)
    data = _parse_json(response.content)
    result = ReviewOutput(**data)

    if result.is_stale:
        count_score = min(dim.update_count / 10, 1.0)
        new_confidence = count_score * 0.4 + result.new_consistency_score * 0.6
        entry = HistoryEntry(
            version=dim.update_count + 1,
            change=f"定时复审：{result.reason}",
            trigger=f"超过 {days_since_last_signal} 天无新信号",
            confidence=new_confidence,
            updated_at=datetime.now(timezone.utc),
        )
        self._mgr.update(
            name=dimension,
            new_content=dim.content,
            history_entry=entry,
            confidence=new_confidence,
        )

    return result
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/unit/layers/growth/test_telos_engine.py::TestReviewStaleDimension -v
```

**Step 5: 提交**

```bash
git add huaqi_src/layers/growth/telos/engine.py tests/unit/layers/growth/test_telos_engine.py
git commit -m "feat(telos): add review_stale_dimension for periodic staleness check"
```

---

### Task 5.2：创建 ReviewJob

**Step 1: 在 test_growth_jobs.py 追加测试**

```python
class TestReviewJob:
    def test_review_job_calls_engine_for_stale_dimensions(self, tmp_path):
        from huaqi_src.scheduler.review_job import run_review_job
        from unittest.mock import MagicMock, patch
        from datetime import datetime, timezone, timedelta

        mock_engine = MagicMock()
        mock_engine.review_stale_dimension.return_value = MagicMock(is_stale=False)

        mock_mgr = MagicMock()
        from huaqi_src.layers.growth.telos.models import DimensionLayer
        from huaqi_src.layers.growth.telos.models import TelosDimension
        stale_dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="当前内容",
            confidence=0.8,
        )
        mock_mgr.list_active.return_value = [stale_dim]

        stale_date = datetime.now(timezone.utc) - timedelta(days=35)

        with patch("huaqi_src.scheduler.review_job._get_engine_and_manager", return_value=(mock_engine, mock_mgr)):
            with patch("huaqi_src.scheduler.review_job._get_dimension_last_updated", return_value=stale_date):
                result = run_review_job(stale_threshold_days=30)

        assert result["reviewed"] >= 1
        mock_engine.review_stale_dimension.assert_called()
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/unit/scheduler/test_growth_jobs.py::TestReviewJob -v
```

**Step 3: 创建 review_job.py**

创建 `huaqi_src/scheduler/review_job.py`：

```python
from datetime import datetime, timezone, timedelta
from typing import Any, Dict


def _get_engine_and_manager():
    from huaqi_src.config.paths import get_telos_dir, get_db_path
    from huaqi_src.layers.growth.telos.engine import TelosEngine
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.cli.context import build_llm_manager

    telos_dir = get_telos_dir()
    telos_mgr = TelosManager(telos_dir=telos_dir, git_commit=True)

    llm_mgr = build_llm_manager(temperature=0.3, max_tokens=1000)
    if llm_mgr is None:
        raise RuntimeError("未配置 LLM")

    active_name = llm_mgr.get_active_provider()
    cfg = llm_mgr._configs[active_name]
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.api_base or None,
        temperature=0.3,
        max_tokens=1000,
    )
    engine = TelosEngine(telos_manager=telos_mgr, llm=llm)
    return engine, telos_mgr


def _get_dimension_last_updated(telos_dir, name: str) -> datetime:
    import re
    from pathlib import Path
    p = Path(telos_dir) / f"{name}.md"
    if not p.exists():
        return datetime.now(timezone.utc) - timedelta(days=999)
    text = p.read_text(encoding="utf-8")
    m = re.search(r"updated_at: (\d{4}-\d{2}-\d{2})", text)
    if m:
        return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - timedelta(days=999)


def run_review_job(
    stale_threshold_days: int = 30,
) -> Dict[str, Any]:
    engine, telos_mgr = _get_engine_and_manager()
    now = datetime.now(timezone.utc)

    reviewed = 0
    stale_found = 0

    for dim in telos_mgr.list_active():
        last_updated = _get_dimension_last_updated(telos_mgr._dir, dim.name)
        days_since = (now - last_updated).days
        if days_since >= stale_threshold_days:
            try:
                result = engine.review_stale_dimension(dim.name, days_since_last_signal=days_since)
                reviewed += 1
                if result.is_stale:
                    stale_found += 1
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"复审失败 dim={dim.name}: {e}")

    return {"reviewed": reviewed, "stale_found": stale_found}
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/unit/scheduler/test_growth_jobs.py::TestReviewJob -v
```

**Step 5: 提交**

```bash
git add huaqi_src/scheduler/review_job.py tests/unit/scheduler/test_growth_jobs.py
git commit -m "feat(scheduler): add ReviewJob for periodic stale dimension check"
```

---

## Task 6：冷启动问卷升级（5个问题 + 置信度 0.4）

**背景：** 当前冷启动问卷已有基础实现（10个问题，置信度0.5），根据设计文档需要：
1. 问题从10个压缩为5个，每个覆盖1-2个维度
2. 初始置信度从 0.5 改为 0.4（标记为"问卷初始化，待验证"）
3. 一次 LLM 调用批量提取所有维度

**注意：** 先检查现有测试 `tests/integration/test_cold_start.py`，当前测试期望10个问题。修改时需要同步更新测试。

**Files:**
- Modify: `huaqi_src/layers/capabilities/onboarding/questionnaire.py`（问题列表改为5个）
- Modify: `huaqi_src/layers/capabilities/onboarding/telos_generator.py`（置信度改为 0.4）
- Modify: `tests/integration/test_cold_start.py`（更新期望值）

---

### Task 6.1：问题列表改为5个高密度问题

**Step 1: 更新测试期望值**

在 `tests/integration/test_cold_start.py` 的 `TestOnboardingQuestions` 类中，将：
```python
def test_ten_questions_defined(self):
    assert len(ONBOARDING_QUESTIONS) == 10
```
改为：
```python
def test_five_questions_defined(self):
    assert len(ONBOARDING_QUESTIONS) == 5
```

同时将：
```python
def test_meta_is_last_question(self):
    assert ONBOARDING_QUESTIONS[-1].dimension == "meta"
```
改为：
```python
def test_people_is_last_question(self):
    assert ONBOARDING_QUESTIONS[-1].dimension == "people"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/integration/test_cold_start.py::TestOnboardingQuestions -v
```

**Step 3: 修改 questionnaire.py**

将 `ONBOARDING_QUESTIONS` 列表替换为5个高密度问题：

```python
ONBOARDING_QUESTIONS: List[Question] = [
    Question(
        dimension="goals",
        text="你现在最想做成的一件事是什么？是什么在阻止你？",
    ),
    Question(
        dimension="beliefs",
        text="你觉得一个人要做成事，最关键的是什么？",
    ),
    Question(
        dimension="narratives",
        text="你怎么描述自己？有没有一面是你不太愿意承认但确实存在的？",
    ),
    Question(
        dimension="strategies",
        text="你现在用什么方式推进事情？最近学到了什么让你觉得有用？",
    ),
    Question(
        dimension="people",
        text="你生活里现在最重要的1-2个人是谁？你们的关系是什么状态？",
    ),
]
```

**Step 4: 更新其他依赖问题数量的测试**

在 `TestOnboardingSession` 中，将 `for _ in ONBOARDING_QUESTIONS:` 相关的测试检查更新为期望完成5个问题后 `is_complete() == True`。

**Step 5: 运行测试确认通过**

```bash
pytest tests/integration/test_cold_start.py::TestOnboardingQuestions -v
pytest tests/integration/test_cold_start.py::TestOnboardingSession -v
```

**Step 6: 提交**

```bash
git add huaqi_src/layers/capabilities/onboarding/questionnaire.py tests/integration/test_cold_start.py
git commit -m "feat(onboarding): compress to 5 high-density questions covering 8 dimensions"
```

---

### Task 6.2：初始置信度改为 0.4

**Step 1: 更新测试期望**

在 `tests/integration/test_cold_start.py` 的 `TestOnboardingTelosGenerator` 中，将：
```python
assert goals_dim.confidence == 0.5
```
全部改为：
```python
assert goals_dim.confidence == 0.4
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/integration/test_cold_start.py::TestOnboardingTelosGenerator -v
```

**Step 3: 修改 telos_generator.py**

在 `telos_generator.py` 中，将所有 `confidence=0.5` 改为 `confidence=0.4`。

**Step 4: 运行测试确认通过**

```bash
pytest tests/integration/test_cold_start.py::TestOnboardingTelosGenerator -v
```

**Step 5: 运行全量集成测试**

```bash
pytest tests/integration/ -v
```

**Step 6: 提交**

```bash
git add huaqi_src/layers/capabilities/onboarding/telos_generator.py tests/integration/test_cold_start.py
git commit -m "feat(onboarding): set initial confidence to 0.4 (survey-initialized, pending verification)"
```

---

## Task 7：真实 LLM 集成验证（端到端冒烟测试）

**这是最后一个任务，也是最重要的验证。** 前面所有 Task 都使用 MagicMock，从未验证真实 LLM 调用。

**注意：** 此任务需要有效的 LLM 配置（deepseek-chat 或其他），会产生 API 费用。

**Files:**
- Create: `tests/e2e/test_telos_e2e.py`

---

### Task 7.1：端到端冒烟测试

**Step 1: 写 e2e 测试**

创建 `tests/e2e/test_telos_e2e.py`：

```python
"""
端到端测试：真实 LLM 验证 Telos 流水线

需要有效的 LLM 配置才能运行。
运行方式：pytest tests/e2e/ -v -m e2e
"""
import pytest
from pathlib import Path
from datetime import datetime, timezone


pytestmark = pytest.mark.e2e


@pytest.fixture
def telos_dir(tmp_path: Path) -> Path:
    d = tmp_path / "telos"
    d.mkdir()
    return d


@pytest.fixture
def real_llm():
    try:
        from huaqi_src.cli.context import build_llm_manager, ensure_initialized
        ensure_initialized()
        llm_mgr = build_llm_manager(temperature=0.3, max_tokens=2000)
        if llm_mgr is None:
            pytest.skip("未配置 LLM")
        active_name = llm_mgr.get_active_provider()
        cfg = llm_mgr._configs[active_name]
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.3,
            max_tokens=2000,
        )
    except Exception as e:
        pytest.skip(f"LLM 配置失败: {e}")


def test_step1_real_llm_parses_journal(telos_dir, real_llm):
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.engine import TelosEngine, Step1Output, SignalStrength
    from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

    mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
    mgr.init()
    engine = TelosEngine(telos_manager=mgr, llm=real_llm)

    signal = RawSignal(
        user_id="user_e2e",
        source_type=SourceType.JOURNAL,
        timestamp=datetime.now(timezone.utc),
        content="今天突然想清楚了一件事：我一直在拼命努力，但从来没有停下来想方向对不对。感觉选错了方向，努力是白费的。",
    )

    result = engine.step1_analyze(signal)

    assert isinstance(result, Step1Output)
    assert len(result.dimensions) > 0
    assert any(d in ["challenges", "goals", "beliefs"] for d in result.dimensions)
    assert result.signal_strength in [SignalStrength.STRONG, SignalStrength.MEDIUM]


def test_step345_combined_real_llm(telos_dir, real_llm):
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.engine import TelosEngine, CombinedStepOutput

    mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
    mgr.init()
    engine = TelosEngine(telos_manager=mgr, llm=real_llm)

    result = engine.step345_combined(
        dimension="challenges",
        signal_summaries=[
            "用户对方向感感到迷茫，质疑努力的意义",
            "用户觉得选错了方向，努力都是白费的",
            "用户想停下来重新思考目标和方向",
        ],
        days=7,
        recent_signal_count=3,
    )

    assert isinstance(result, CombinedStepOutput)
    assert isinstance(result.should_update, bool)
    assert 0.0 <= result.confidence <= 1.0
    assert 0.0 <= result.consistency_score <= 1.0


def test_telos_snapshot_in_agent_context_real_llm(telos_dir, real_llm):
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.engine import TelosEngine
    from huaqi_src.layers.growth.telos.context import TelosContextBuilder

    mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
    mgr.init()
    engine = TelosEngine(telos_manager=mgr, llm=real_llm)

    engine.step345_combined(
        dimension="beliefs",
        signal_summaries=["选择比努力重要", "方向错了努力没用"],
        days=7,
        recent_signal_count=2,
    )

    builder = TelosContextBuilder(telos_manager=mgr)
    snapshot = builder.build_telos_snapshot()

    assert "beliefs" in snapshot
    assert len(snapshot) > 50
```

**Step 2: 在 pyproject.toml 中注册 e2e marker**

查看 `pyproject.toml` 的 `[tool.pytest.ini_options]` 部分，追加：
```toml
markers = [
    "e2e: end-to-end tests requiring real LLM (deselect with '-m not e2e')",
]
```

**Step 3: 运行 e2e 测试**

```bash
pytest tests/e2e/test_telos_e2e.py -v -m e2e
```
预期：所有测试 PASSED（需要有效 LLM）

**Step 4: 确认 unit 测试不受影响**

```bash
pytest tests/unit/ tests/integration/ -v -m "not e2e"
```

**Step 5: 提交**

```bash
git add tests/e2e/test_telos_e2e.py pyproject.toml
git commit -m "test(e2e): add real LLM e2e smoke tests for Telos pipeline"
```

---

## 快速参考

### 关键文件路径速查

| 要修改什么 | 文件 |
|-----------|------|
| Agent 接入 Telos | `huaqi_src/agent/nodes/chat_nodes.py` |
| Telos 快照构建 | `huaqi_src/layers/growth/telos/context.py` |
| 维度片段读取 | `huaqi_src/layers/growth/telos/manager.py` |
| 合并流水线步骤 | `huaqi_src/layers/growth/telos/engine.py` |
| 自动提炼触发 | `huaqi_src/scheduler/distillation_job.py` (新建) |
| 维度独立（移除 people） | `huaqi_src/layers/growth/telos/models.py` |
| People 分叉调用 | `huaqi_src/layers/data/raw_signal/pipeline.py` |
| 定时复审 | `huaqi_src/scheduler/review_job.py` (新建) |
| 冷启动问卷 | `huaqi_src/layers/capabilities/onboarding/questionnaire.py` |
| 冷启动置信度 | `huaqi_src/layers/capabilities/onboarding/telos_generator.py` |
| e2e 测试 | `tests/e2e/test_telos_e2e.py` (新建) |

### 常用测试命令

```bash
pytest tests/unit/layers/growth/ -v
pytest tests/unit/agent/ -v
pytest tests/integration/ -v
pytest tests/unit/scheduler/ -v
pytest tests/e2e/ -v -m e2e
pytest tests/ -v --ignore=tests/e2e/
```

### 任务依赖关系

```
Task 1 (Agent 接入) → 独立可做
Task 2 (自动提炼) → 独立可做
Task 3 (合并流水线) → Task 3.2 依赖 Task 3.1
Task 4 (People 独立) → 建议在 Task 3 之后做
Task 5 (定时复审) → 建议在 Task 3 之后做
Task 6 (冷启动升级) → 独立可做
Task 7 (e2e 验证) → 依赖 Task 1、2、3 全部完成
```
