# Remaining Features Implementation Plan

**Goal:** 补全验收清单中所有 ❌ 未实现和 ⚠️ 部分实现的功能，使系统达到完整可用状态。

**Architecture:** 按依赖关系从底层到上层分 6 个 Phase 实现：先修 ruff/代码规范（Phase 1），再补管道层 bug（Phase 2），再实现多用户/抽象接口（Phase 3），再补 scheduler/Git/通知（Phase 4），再实现 Agent 工作模式（Phase 5），最后实现数据采集 converters（Phase 6）。每个 Task 先写测试再写实现（TDD）。

**Tech Stack:** Python 3.9, Pydantic v2, SQLite, LangGraph, GitPython, APScheduler, Typer, pytest

---

## 背景：当前状态

已完成（Phase 1~4 共 219 tests）：
- RAW_SIGNAL 模型/存储/管道骨架（`layers/data/raw_signal/`）
- TELOS 模型/管理器/引擎(5步)/成长事件/META/上下文构建（`layers/growth/telos/`）
- 冷启动问卷状态机 + TELOS 生成（`layers/capabilities/onboarding/`）
- 成长报告 + 学习追踪（`layers/capabilities/reports/` / `layers/capabilities/learning/`）

**测试命令：**
```bash
pytest tests/unit/ tests/integration/ -x -q
```

**ruff 路径：**
```bash
/Users/lianzimeng/Library/Python/3.9/bin/ruff
```

---

## Phase 1：代码规范修复（ruff + __init__.py）

> 前置：不修就无法保证后续代码质量。估时 30 分钟。

### Task 1.1：修复 ruff 错误

**Files:**
- Modify: `huaqi_src/config/errors.py`（E701：单行多语句）
- Modify: `huaqi_src/layers/` 下各文件（F401 未使用导入、F841 未使用变量）

**Step 1：确认当前错误数**

```bash
/Users/lianzimeng/Library/Python/3.9/bin/ruff check huaqi_src/config/errors.py
/Users/lianzimeng/Library/Python/3.9/bin/ruff check huaqi_src/layers/ huaqi_src/config/adapters/ huaqi_src/agent/state.py
```

**Step 2：修改 errors.py（每个 class 独占一行，消除 E701）**

```python
# huaqi_src/config/errors.py
from typing import Optional


class HuaqiError(Exception):
    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message)
        self.context = context or {}


class StorageError(HuaqiError):
    pass


class SignalNotFoundError(StorageError):
    pass


class SignalDuplicateError(StorageError):
    pass


class VectorError(HuaqiError):
    pass


class VectorUpsertError(VectorError):
    pass


class TelosError(HuaqiError):
    pass


class DimensionNotFoundError(TelosError):
    pass


class DimensionParseError(TelosError):
    pass


class DistillationError(HuaqiError):
    pass


class AnalysisError(DistillationError):
    pass


class UpdateGenerationError(DistillationError):
    pass


class SchedulerError(HuaqiError):
    pass


class InterfaceError(HuaqiError):
    pass


class AgentError(HuaqiError):
    pass


class IntentParseError(AgentError):
    pass


class UserError(HuaqiError):
    pass


class UserNotFoundError(UserError):
    pass
```

**Step 3：自动修复 F401/F841**

```bash
/Users/lianzimeng/Library/Python/3.9/bin/ruff check huaqi_src/layers/ huaqi_src/config/ huaqi_src/agent/state.py --fix
```

**Step 4：手动修复剩余错误**

`huaqi_src/layers/growth/telos/engine.py` 中删除未使用变量（具体行号以 ruff 输出为准）：
```python
# 删除未使用的 layer 变量赋值，直接使用 STANDARD_DIMENSION_LAYERS.get() 返回值
```

**Step 5：验证零错误**

```bash
/Users/lianzimeng/Library/Python/3.9/bin/ruff check huaqi_src/layers/ huaqi_src/config/ huaqi_src/agent/state.py
```

Expected: `All checks passed!`

**Step 6：回归测试**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

Expected: 219 passed

---

### Task 1.2：填充各模块 __init__.py 公开接口

**Files:**
- Modify: `huaqi_src/layers/data/raw_signal/__init__.py`
- Modify: `huaqi_src/layers/growth/telos/__init__.py`
- Modify: `huaqi_src/layers/capabilities/onboarding/__init__.py`
- Modify: `huaqi_src/layers/capabilities/reports/__init__.py`
- Modify: `huaqi_src/layers/capabilities/learning/__init__.py`
- Modify: `huaqi_src/config/adapters/__init__.py`

**Step 1：raw_signal __init__.py**

```python
# huaqi_src/layers/data/raw_signal/__init__.py
from .models import RawSignal, RawSignalFilter, SourceType
from .store import RawSignalStore
from .pipeline import DistillationPipeline

__all__ = ["RawSignal", "RawSignalFilter", "SourceType", "RawSignalStore", "DistillationPipeline"]
```

**Step 2：telos __init__.py**

```python
# huaqi_src/layers/growth/telos/__init__.py
from .models import TelosDimension, DimensionLayer, HistoryEntry, STANDARD_DIMENSIONS
from .manager import TelosManager
from .engine import TelosEngine, Step1Output, Step3Output, Step4Output, Step5Output, SignalStrength, UpdateType
from .growth_events import GrowthEvent, GrowthEventStore
from .meta import MetaManager, CorrectionRecord, DimensionOperation
from .context import TelosContextBuilder, SystemPromptBuilder

__all__ = [
    "TelosDimension", "DimensionLayer", "HistoryEntry", "STANDARD_DIMENSIONS",
    "TelosManager", "TelosEngine",
    "Step1Output", "Step3Output", "Step4Output", "Step5Output",
    "SignalStrength", "UpdateType",
    "GrowthEvent", "GrowthEventStore",
    "MetaManager", "CorrectionRecord", "DimensionOperation",
    "TelosContextBuilder", "SystemPromptBuilder",
]
```

**Step 3：其余 __init__.py**（参照上述格式暴露各自的核心类）

**Step 4：验证 import 正常**

```bash
python3 -c "from huaqi_src.layers.data.raw_signal import RawSignal, RawSignalStore; print('OK')"
python3 -c "from huaqi_src.layers.growth.telos import TelosManager, TelosEngine; print('OK')"
```

Expected: 两行都输出 `OK`

---

## Phase 2：管道层 Bug 修复

> 修复验收清单中的 ⚠️ 部分实现问题，不新增功能。估时 45 分钟。

### Task 2.1：Step2 时间窗口过滤（DistillationPipeline）

**背景：** `pipeline.py:process()` 中查询已处理信号时未传 `timestamp_after`，导致全量计数，忽略了 `days_window` 配置。

**Files:**
- Modify: `huaqi_src/layers/data/raw_signal/pipeline.py`（`process()` 方法，约第 44 行的 `count()` 和 `query()` 调用）
- Create: `tests/unit/layers/data/test_raw_signal_pipeline.py`

**Step 1：写失败测试**

```python
# tests/unit/layers/data/test_raw_signal_pipeline.py
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.growth_events import GrowthEventStore
from huaqi_src.layers.growth.telos.engine import TelosEngine, Step1Output, SignalStrength


def make_pipeline(tmp_path: Path, days_window: int = 30):
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    store = RawSignalStore(adapter=adapter)
    telos_dir = tmp_path / "telos"
    telos_manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    telos_manager.init()
    event_store = GrowthEventStore(db_path=tmp_path / "test.db")
    mock_llm = MagicMock()
    engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
    return DistillationPipeline(
        signal_store=store,
        event_store=event_store,
        telos_manager=telos_manager,
        engine=engine,
        signal_threshold=2,
        days_window=days_window,
    ), store


def test_pipeline_step2_only_queries_within_days_window(tmp_path):
    """聚合查询应只取 days_window 内的信号，窗口外的不计入阈值"""
    pipeline, store = make_pipeline(tmp_path, days_window=7)

    now = datetime.now(timezone.utc)
    old_signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=now - timedelta(days=10),  # 超出 7 天窗口
        content="很久以前的日记",
    )
    store.save(old_signal)
    store.mark_processed(old_signal.id)

    new_signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=now - timedelta(days=1),
        content="今天的日记",
    )
    store.save(new_signal)

    mock_llm = pipeline._engine._llm
    mock_llm.invoke.return_value = MagicMock(
        content='{"dimensions":["goals"],"emotion":"positive","intensity":0.6,"signal_strength":"medium","strong_reason":null,"summary":"今天的日记","new_dimension_hint":null}'
    )

    result = pipeline.process(new_signal)
    # 窗口内只有 1 条已处理信号，threshold=2，不满足，pipeline_runs 应为空
    assert result["pipeline_runs"] == []
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/layers/data/test_raw_signal_pipeline.py::test_pipeline_step2_only_queries_within_days_window -v
```

Expected: FAIL（当前 `count()` 无时间过滤，会把 old_signal 算进去）

**Step 3：修复 pipeline.py**

在 `process()` 方法开头添加时间窗口计算，并在 `count()` 和 `query()` 调用中传入 `timestamp_after`：

```python
# huaqi_src/layers/data/raw_signal/pipeline.py
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter
# ... 其余 import 不变

def process(self, signal: RawSignal) -> Dict[str, Any]:
    step1_result = self._engine.step1_analyze(signal)
    self._signal_store.mark_processed(signal.id)

    results: Dict[str, Any] = {
        "signal_id": signal.id,
        "step1": step1_result,
        "pipeline_runs": [],
    }

    since = datetime.now(timezone.utc) - timedelta(days=self._days_window)  # 加这一行

    for dimension in step1_result.dimensions:
        count = self._signal_store.count(
            RawSignalFilter(
                user_id=signal.user_id,
                processed=1,
                timestamp_after=since,  # 修改：加时间窗口
            )
        )
        if count < self._threshold:
            continue

        unprocessed = self._signal_store.query(
            RawSignalFilter(
                user_id=signal.user_id,
                processed=1,
                timestamp_after=since,  # 修改：加时间窗口
                limit=self._threshold * 3,
            )
        )
        # 后续逻辑不变
```

注意：`RawSignalFilter` 中字段名为 `timestamp_after`，与 `SQLiteStorageAdapter` 中的查询字段保持一致（需确认 `storage.py` WHERE 子句）。

**Step 4：运行测试**

```bash
pytest tests/unit/layers/data/test_raw_signal_pipeline.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

Expected: 220+ passed

---

### Task 2.2：强信号绕过阈值直通

**背景：** `pipeline.py:process()` 中无强信号判断，`signal_strength=STRONG` 的信号也需要等待阈值积累才触发，失去了「强信号立即处理」的语义。

**Files:**
- Modify: `huaqi_src/layers/data/raw_signal/pipeline.py`（在阈值判断前加 `is_strong` 分支）
- Modify: `tests/unit/layers/data/test_raw_signal_pipeline.py`（新增测试）

**Step 1：写失败测试**

```python
# 追加到 tests/unit/layers/data/test_raw_signal_pipeline.py

def test_pipeline_strong_signal_bypasses_threshold(tmp_path):
    """强信号（signal_strength=STRONG）应绕过阈值检查直接进入 run_pipeline"""
    pipeline, store = make_pipeline(tmp_path, days_window=30)
    # 只有 1 条已处理信号，threshold=2，正常逻辑不应触发
    now = datetime.now(timezone.utc)
    signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=now,
        content="我彻底改变了对人生的看法，这是一个重大转折点",
    )
    store.save(signal)

    mock_llm = pipeline._engine._llm
    mock_llm.invoke.return_value = MagicMock(
        content='{"dimensions":["beliefs"],"emotion":"positive","intensity":0.95,"signal_strength":"strong","strong_reason":"用户明确表达了根本性转变","summary":"人生观转变","new_dimension_hint":null}'
    )

    result = pipeline.process(signal)
    # 强信号即使只有 1 条也应进入 pipeline_runs
    assert len(result["pipeline_runs"]) > 0
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/layers/data/test_raw_signal_pipeline.py::test_pipeline_strong_signal_bypasses_threshold -v
```

**Step 3：修复 pipeline.py**

在 Task 2.1 修改基础上，继续修改 `process()` 中的阈值判断：

```python
from huaqi_src.layers.growth.telos.engine import SignalStrength

for dimension in step1_result.dimensions:
    is_strong = step1_result.signal_strength == SignalStrength.STRONG

    count = self._signal_store.count(
        RawSignalFilter(user_id=signal.user_id, processed=1, timestamp_after=since)
    )

    # 强信号直通，不检查阈值
    if not is_strong and count < self._threshold:
        continue
    # ... 后续不变
```

**Step 4：运行全部 pipeline 测试**

```bash
pytest tests/unit/layers/data/test_raw_signal_pipeline.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

### Task 2.3：INDEX.md 添加内容摘要

**背景：** `TelosManager._rebuild_index()` 中每条记录只有版本号和置信度，缺少维度内容摘要（前30字），导致 INDEX.md 无法快速了解各维度状态。

**Files:**
- Modify: `huaqi_src/layers/growth/telos/manager.py`（`_rebuild_index()` 方法，约第 144 行的 `dim_line` 格式）
- Modify: `tests/unit/layers/growth/test_telos_manager.py`（新增测试）

**Step 1：写失败测试**

```python
# 追加到 tests/unit/layers/growth/test_telos_manager.py

def test_index_md_contains_content_summary(tmp_path):
    """INDEX.md 每条记录应包含维度内容摘要（前30字）"""
    telos_dir = tmp_path / "telos"
    manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    manager.init()

    from huaqi_src.layers.growth.telos.models import HistoryEntry
    from datetime import datetime, timezone
    manager.update(
        "beliefs",
        new_content="选择比努力更重要，在正确方向上努力才有复利效应",
        history_entry=HistoryEntry(
            version=1, change="初始化", trigger="问卷",
            confidence=0.5, updated_at=datetime.now(timezone.utc)
        ),
        confidence=0.5,
    )

    index = (telos_dir / "INDEX.md").read_text(encoding="utf-8")
    assert "选择比努力更重要" in index
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/layers/growth/test_telos_manager.py::test_index_md_contains_content_summary -v
```

Expected: FAIL（当前 `_rebuild_index` 不含内容摘要）

**Step 3：修改 `_rebuild_index`**

将当前的 `f"- [{d.name}.md]({d.name}.md) — v{d.update_count}，置信度 {d.confidence}"` 替换为含摘要的格式：

```python
def _rebuild_index(self) -> None:
    active = self.list_active()
    core = [d for d in active if d.layer == DimensionLayer.CORE]
    middle = [d for d in active if d.layer == DimensionLayer.MIDDLE]
    surface = [d for d in active if d.layer == DimensionLayer.SURFACE]

    lines = [
        "# TELOS 索引",
        "",
        f"> 最后更新：{datetime.now(timezone.utc).strftime('%Y-%m-%d')} · 共 {len(active)} 个活跃维度",
        "",
        "## 核心层（变化最慢）",
    ]

    def dim_line(d: TelosDimension) -> str:
        summary = d.content[:30].replace("\n", " ") + ("…" if len(d.content) > 30 else "")
        return f"- [{d.name}.md]({d.name}.md) — {summary}（v{d.update_count}，置信度 {d.confidence}）"

    for d in core:
        lines.append(dim_line(d))

    lines += ["", "## 中间层（定期变化）"]
    for d in middle:
        lines.append(dim_line(d))

    lines += ["", "## 表面层（频繁变化）"]
    for d in surface:
        lines.append(dim_line(d))

    lines += ["", "## 特殊", "- [meta.md](meta.md)", ""]
    (self._dir / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
```

**Step 4：运行测试**

```bash
pytest tests/unit/layers/growth/test_telos_manager.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

### Task 2.4：TelosManager 自动联动 MetaManager

**背景：** `TelosManager.archive()` 和 `create_custom()` 执行后需在 meta.md 记录维度演化，但目前二者均无 `meta_manager` 参数，调用方必须手动调用 `MetaManager.log_dimension_operation()`。

**Files:**
- Modify: `huaqi_src/layers/growth/telos/manager.py`（`create_custom()` / `archive()` 添加可选 `meta_manager` 参数）
- Modify: `tests/unit/layers/growth/test_telos_manager.py`（新增测试）

**Step 1：写失败测试**

```python
# 追加到 tests/unit/layers/growth/test_telos_manager.py
from huaqi_src.layers.growth.telos.meta import MetaManager

def test_create_custom_logs_to_meta(tmp_path):
    """create_custom 后 meta.md 的维度演化历史应自动新增记录"""
    telos_dir = tmp_path / "telos"
    manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    manager.init()
    meta = MetaManager(telos_dir / "meta.md")
    initial_ops = meta.list_dimension_operations()

    from huaqi_src.layers.growth.telos.models import DimensionLayer
    manager.create_custom("health", DimensionLayer.MIDDLE, "关注身体状态", meta_manager=meta)

    ops = meta.list_dimension_operations()
    assert len(ops) == len(initial_ops) + 1
    assert ops[-1].dimension == "health"
    assert ops[-1].operation == "add"


def test_archive_logs_to_meta(tmp_path):
    """archive 后 meta.md 的维度演化历史应自动新增记录"""
    telos_dir = tmp_path / "telos"
    manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    manager.init()
    from huaqi_src.layers.growth.telos.models import DimensionLayer
    meta = MetaManager(telos_dir / "meta.md")
    manager.create_custom("health", DimensionLayer.MIDDLE, "关注身体状态", meta_manager=meta)

    manager.archive("health", meta_manager=meta)

    ops = meta.list_dimension_operations()
    archive_ops = [o for o in ops if o.operation == "archive"]
    assert len(archive_ops) == 1
    assert archive_ops[0].dimension == "health"
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/layers/growth/test_telos_manager.py::test_create_custom_logs_to_meta tests/unit/layers/growth/test_telos_manager.py::test_archive_logs_to_meta -v
```

Expected: FAIL（`create_custom` / `archive` 不接受 `meta_manager` 参数）

**Step 3：修改 TelosManager**

```python
# huaqi_src/layers/growth/telos/manager.py
# 在文件顶部添加 TYPE_CHECKING 导入（避免循环依赖）
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from huaqi_src.layers.growth.telos.meta import MetaManager, DimensionOperation

def create_custom(
    self,
    name: str,
    layer: DimensionLayer,
    initial_content: str,
    meta_manager: Optional["MetaManager"] = None,
) -> None:
    p = self._path(name)
    if p.exists():
        raise ValueError(f"Dimension '{name}' already exists")
    dim = TelosDimension(
        name=name,
        layer=layer,
        content=initial_content,
        confidence=0.5,
        is_custom=True,
    )
    p.write_text(dim.to_markdown(), encoding="utf-8")
    self._rebuild_index()
    if meta_manager is not None:
        from huaqi_src.layers.growth.telos.meta import DimensionOperation
        meta_manager.add_active_dimension(name)
        meta_manager.log_dimension_operation(DimensionOperation(
            dimension=name,
            operation="add",
            date=datetime.now(timezone.utc),
            reason="用户创建自定义维度",
        ))


def archive(
    self,
    name: str,
    meta_manager: Optional["MetaManager"] = None,
) -> None:
    if name in STANDARD_DIMENSIONS:
        raise ValueError(f"Cannot archive standard dimension '{name}'")
    p = self._path(name)
    if not p.exists():
        raise DimensionNotFoundError(f"Dimension '{name}' not found")
    dest = self._archive_path(name)
    shutil.move(str(p), str(dest))
    self._rebuild_index()
    if meta_manager is not None:
        from huaqi_src.layers.growth.telos.meta import DimensionOperation
        meta_manager.remove_active_dimension(name)
        meta_manager.log_dimension_operation(DimensionOperation(
            dimension=name,
            operation="archive",
            date=datetime.now(timezone.utc),
            reason="用户归档维度",
        ))
```

**Step 4：运行测试**

```bash
pytest tests/unit/layers/growth/test_telos_manager.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

### Task 2.5：用户纠错后 confidence 下调

**背景：** `MetaManager.add_correction()` 当前签名为 `add_correction(self, record: CorrectionRecord)`，不接受 `dimension` 和 `telos_manager` 参数，无法联动下调对应维度置信度。

**Files:**
- Modify: `huaqi_src/layers/growth/telos/meta.py`（`add_correction()` 添加可选参数）
- Modify: `tests/unit/layers/growth/test_meta.py`（新增测试）

**Step 1：写失败测试**

```python
# 追加到 tests/unit/layers/growth/test_meta.py

def test_correction_reduces_dimension_confidence(tmp_path):
    """用户纠错后，对应维度的 confidence 应被下调"""
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.models import HistoryEntry, DimensionLayer
    from huaqi_src.layers.growth.telos.meta import MetaManager, CorrectionRecord
    from datetime import datetime, timezone

    telos_dir = tmp_path / "telos"
    manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    manager.init()
    manager.update(
        "beliefs",
        new_content="努力一定有回报",
        history_entry=HistoryEntry(version=1, change="初始", trigger="问卷",
                                   confidence=0.8, updated_at=datetime.now(timezone.utc)),
        confidence=0.8,
    )

    meta = MetaManager(telos_dir / "meta.md")
    meta.init(["beliefs"])

    record = CorrectionRecord(
        date=datetime.now(timezone.utc),
        agent_conclusion="努力一定有回报",
        user_feedback="不对，选择比努力更重要",
        correction_direction="修正「努力回报」信念",
    )
    meta.add_correction(record, dimension="beliefs", telos_manager=manager)

    dim = manager.get("beliefs")
    assert dim.confidence < 0.8
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/layers/growth/test_meta.py::test_correction_reduces_dimension_confidence -v
```

**Step 3：修改 meta.py**

```python
# huaqi_src/layers/growth/telos/meta.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from huaqi_src.layers.growth.telos.manager import TelosManager

def add_correction(
    self,
    record: CorrectionRecord,
    dimension: Optional[str] = None,
    telos_manager: Optional["TelosManager"] = None,
    confidence_penalty: float = 0.15,
) -> None:
    """记录用户纠错。若提供 dimension 和 telos_manager，同时下调该维度置信度。"""
    text = self._read()
    row = f"| {record.date.strftime('%Y-%m-%d')} | {record.agent_conclusion} | {record.user_feedback} | {record.correction_direction} |"
    text = text.replace(
        "| 日期 | Agent 提炼结论 | 用户反馈 | 校正方向 |\n|---|---|---|---|",
        f"| 日期 | Agent 提炼结论 | 用户反馈 | 校正方向 |\n|---|---|---|---|\n{row}",
    )
    self._write(text)

    if dimension and telos_manager:
        try:
            dim = telos_manager.get(dimension)
            new_confidence = max(0.0, dim.confidence - confidence_penalty)
            from huaqi_src.layers.growth.telos.models import HistoryEntry
            entry = HistoryEntry(
                version=dim.update_count + 1,
                change=f"用户纠错：{record.correction_direction}",
                trigger=f"用户反馈：{record.user_feedback}",
                confidence=new_confidence,
                updated_at=datetime.now(timezone.utc),
            )
            telos_manager.update(
                name=dimension,
                new_content=dim.content,
                history_entry=entry,
                confidence=new_confidence,
            )
        except Exception:
            pass
```

**Step 4：运行测试**

```bash
pytest tests/unit/layers/growth/test_meta.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

## Phase 3：多用户管理 + VectorAdapter ABC

> 实现 users.json 多用户 profile，以及正式的 VectorAdapter 抽象接口。估时 1.5 小时。

### Task 3.1：UserProfile + UserContext 模型

**Files:**
- Create: `huaqi_src/config/users.py`
- Create: `tests/unit/config/test_users.py`

**Step 1：写失败测试**

```python
# tests/unit/config/test_users.py
import pytest
from pathlib import Path
from huaqi_src.config.users import UserProfile, UserContext, UserManager


def test_user_manager_creates_profile(tmp_path):
    manager = UserManager(config_dir=tmp_path)
    profile = manager.create("alice")

    assert profile.name == "alice"
    assert len(profile.id) == 36  # UUID4 格式
    assert (tmp_path / "users.json").exists()


def test_user_manager_get_current(tmp_path):
    manager = UserManager(config_dir=tmp_path)
    manager.create("alice")
    current = manager.get_current()
    assert current.name == "alice"


def test_user_manager_switch(tmp_path):
    manager = UserManager(config_dir=tmp_path)
    manager.create("alice")
    manager.create("bob")
    manager.switch("bob")
    assert manager.get_current().name == "bob"


def test_user_context_paths(tmp_path):
    manager = UserManager(config_dir=tmp_path)
    profile = manager.create("alice")
    ctx = UserContext.from_profile(profile, base_dir=tmp_path / "data")

    assert ctx.telos_dir == tmp_path / "data" / "alice" / "telos"
    assert ctx.db_path == tmp_path / "data" / "alice" / "signals.db"
    assert ctx.vector_dir == tmp_path / "data" / "alice" / "vectors"
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/config/test_users.py -v
```

**Step 3：实现 users.py**

```python
# huaqi_src/config/users.py
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel

from huaqi_src.config.errors import UserNotFoundError


class UserProfile(BaseModel):
    id: str
    name: str
    created_at: datetime
    data_dir: str


class UserContext(BaseModel):
    profile: UserProfile
    telos_dir: Path
    raw_files_dir: Path
    db_path: Path
    vector_dir: Path

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_profile(cls, profile: UserProfile, base_dir: Path) -> "UserContext":
        user_dir = base_dir / profile.name
        return cls(
            profile=profile,
            telos_dir=user_dir / "telos",
            raw_files_dir=user_dir / "raw_files",
            db_path=user_dir / "signals.db",
            vector_dir=user_dir / "vectors",
        )


class UserManager:

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._users_file = config_dir / "users.json"

    def _load(self) -> Dict:
        if not self._users_file.exists():
            return {"current": None, "profiles": {}}
        return json.loads(self._users_file.read_text(encoding="utf-8"))

    def _save(self, data: Dict) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._users_file.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )

    def create(self, name: str) -> UserProfile:
        data = self._load()
        if name in data["profiles"]:
            return UserProfile(**data["profiles"][name])
        profile = UserProfile(
            id=str(uuid4()),
            name=name,
            created_at=datetime.now(timezone.utc),
            data_dir=str(Path("~/.huaqi/data") / name),
        )
        data["profiles"][name] = profile.model_dump()
        if data["current"] is None:
            data["current"] = name
        self._save(data)
        return profile

    def get(self, name: str) -> UserProfile:
        data = self._load()
        if name not in data["profiles"]:
            raise UserNotFoundError(f"User '{name}' not found")
        return UserProfile(**data["profiles"][name])

    def get_current(self) -> UserProfile:
        data = self._load()
        if not data["current"]:
            raise UserNotFoundError("No current user set")
        return self.get(data["current"])

    def switch(self, name: str) -> None:
        data = self._load()
        if name not in data["profiles"]:
            raise UserNotFoundError(f"User '{name}' not found")
        data["current"] = name
        self._save(data)

    def list_all(self) -> List[UserProfile]:
        data = self._load()
        return [UserProfile(**p) for p in data["profiles"].values()]
```

**Step 4：运行测试**

```bash
pytest tests/unit/config/test_users.py -v
```

Expected: 4 passed

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

### Task 3.2：VectorAdapter ABC

**Files:**
- Create: `huaqi_src/config/adapters/vector_base.py`
- Create: `huaqi_src/layers/data/memory/models.py`
- Create: `tests/unit/config/test_vector_adapter.py`

**Step 1：写失败测试**

```python
# tests/unit/config/test_vector_adapter.py
import pytest
from huaqi_src.config.adapters.vector_base import VectorAdapter
from huaqi_src.layers.data.memory.models import VectorDocument, VectorQuery, VectorResult


def test_vector_adapter_is_abstract():
    with pytest.raises(TypeError):
        VectorAdapter()


def test_vector_document_model():
    doc = VectorDocument(id="doc1", user_id="u1", content="test content")
    assert doc.id == "doc1"
    assert doc.metadata == {}


def test_vector_query_model():
    q = VectorQuery(user_id="u1", text="搜索词", top_k=3)
    assert q.top_k == 3
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/config/test_vector_adapter.py -v
```

**Step 3：实现**

```python
# huaqi_src/layers/data/memory/models.py
from typing import Dict
from pydantic import BaseModel, Field


class VectorDocument(BaseModel):
    id: str
    user_id: str
    content: str
    metadata: Dict = Field(default_factory=dict)


class VectorQuery(BaseModel):
    user_id: str
    text: str
    top_k: int = 5
    filter: Dict = Field(default_factory=dict)


class VectorResult(BaseModel):
    id: str
    content: str
    metadata: Dict
    score: float
```

```python
# huaqi_src/config/adapters/vector_base.py
from abc import ABC, abstractmethod
from typing import List

from huaqi_src.layers.data.memory.models import VectorDocument, VectorQuery, VectorResult


class VectorAdapter(ABC):

    @abstractmethod
    def upsert(self, doc: VectorDocument) -> None:
        pass

    @abstractmethod
    def upsert_batch(self, docs: List[VectorDocument]) -> None:
        pass

    @abstractmethod
    def query(self, q: VectorQuery) -> List[VectorResult]:
        pass

    @abstractmethod
    def delete(self, doc_id: str, user_id: str) -> None:
        pass
```

**Step 4：运行测试**

```bash
pytest tests/unit/config/test_vector_adapter.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

## Phase 4：Scheduler + Git 集成

> 实现系统的自动化驱动能力。估时 2 小时。

### Task 4.1：SchedulerAdapter ABC + APScheduler 实现

**Files:**
- Create: `huaqi_src/config/adapters/scheduler_base.py`
- Create: `huaqi_src/scheduler/manager.py`（注意：已存在旧版 `scheduler/manager.py`，新实现应替换或新建 `APSchedulerAdapter` 类）
- Create: `tests/unit/config/test_scheduler_adapter.py`

**注意：** 先确认 `huaqi_src/scheduler/manager.py` 现有内容，避免覆盖已有调度逻辑。

**Step 1：写失败测试**

```python
# tests/unit/config/test_scheduler_adapter.py
import pytest
from huaqi_src.config.adapters.scheduler_base import SchedulerAdapter


def test_scheduler_adapter_is_abstract():
    with pytest.raises(TypeError):
        SchedulerAdapter()


def test_scheduler_adapter_interface():
    methods = ["start", "stop", "add_interval_job", "add_cron_job", "remove_job"]
    for m in methods:
        assert hasattr(SchedulerAdapter, m)
```

```python
# tests/unit/config/test_apscheduler.py
import time
from huaqi_src.scheduler.apscheduler_adapter import APSchedulerAdapter


def test_apscheduler_runs_interval_job():
    results = []
    scheduler = APSchedulerAdapter()
    scheduler.start()
    scheduler.add_interval_job(lambda: results.append(1), seconds=1, job_id="test_job")
    time.sleep(2.5)
    scheduler.stop()
    assert len(results) >= 2
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/config/test_scheduler_adapter.py tests/unit/config/test_apscheduler.py -v
```

**Step 3：实现**

```python
# huaqi_src/config/adapters/scheduler_base.py
from abc import ABC, abstractmethod
from typing import Callable


class SchedulerAdapter(ABC):

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def add_interval_job(self, func: Callable, seconds: int, job_id: str) -> None:
        pass

    @abstractmethod
    def add_cron_job(self, func: Callable, cron_expr: str, job_id: str) -> None:
        """cron_expr 格式：'分 时 日 月 周'，如 '0 8 * * *'"""

    @abstractmethod
    def remove_job(self, job_id: str) -> None:
        pass
```

```python
# huaqi_src/scheduler/apscheduler_adapter.py（新建，避免覆盖现有 manager.py）
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from huaqi_src.config.adapters.scheduler_base import SchedulerAdapter


class APSchedulerAdapter(SchedulerAdapter):

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def add_interval_job(self, func: Callable, seconds: int, job_id: str) -> None:
        self._scheduler.add_job(func, "interval", seconds=seconds, id=job_id, replace_existing=True)

    def add_cron_job(self, func: Callable, cron_expr: str, job_id: str) -> None:
        parts = cron_expr.split()
        trigger = CronTrigger(
            minute=parts[0], hour=parts[1],
            day=parts[2], month=parts[3], day_of_week=parts[4],
        )
        self._scheduler.add_job(func, trigger, id=job_id, replace_existing=True)

    def remove_job(self, job_id: str) -> None:
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
```

**Step 4：确认 apscheduler 已安装**

```bash
python3 -c "import apscheduler; print(apscheduler.__version__)"
```

**Step 5：运行测试**

```bash
pytest tests/unit/config/test_scheduler_adapter.py tests/unit/config/test_apscheduler.py -v
```

**Step 6：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

### Task 4.2：定时任务：批量处理积压信号

**Files:**
- Create: `huaqi_src/scheduler/jobs.py`（注意：已存在旧版 `scheduler/jobs.py`，需先阅读再决定追加或替换）
- Modify: `tests/scheduler/test_jobs.py`（追加新测试，避免破坏现有测试）

**注意：** 先阅读现有 `huaqi_src/scheduler/jobs.py` 内容，仅新增 `process_pending_signals_job` 和 `vectorize_pending_signals_job` 函数。

**Step 1：写失败测试**

```python
# 追加到 tests/scheduler/test_jobs.py（或新建 tests/scheduler/test_growth_jobs.py）
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from pathlib import Path

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
from huaqi_src.scheduler.jobs import process_pending_signals_job


def test_process_pending_signals_job_calls_pipeline(tmp_path):
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    store = RawSignalStore(adapter=adapter)

    for i in range(3):
        store.save(RawSignal(
            user_id="u1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content=f"待处理信号 {i}",
        ))

    mock_pipeline = MagicMock()
    process_pending_signals_job(signal_store=store, pipeline=mock_pipeline, user_id="u1", batch_size=10)
    assert mock_pipeline.process.call_count == 3


def test_process_pending_signals_job_skips_processed(tmp_path):
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    store = RawSignalStore(adapter=adapter)

    signal = RawSignal(
        user_id="u1", source_type=SourceType.JOURNAL,
        timestamp=datetime.now(timezone.utc), content="已处理信号",
    )
    store.save(signal)
    store.mark_processed(signal.id)

    mock_pipeline = MagicMock()
    process_pending_signals_job(signal_store=store, pipeline=mock_pipeline, user_id="u1", batch_size=10)
    mock_pipeline.process.assert_not_called()
```

**Step 2：运行确认失败**

```bash
pytest tests/scheduler/ -k "process_pending_signals" -v
```

**Step 3：在现有 jobs.py 中追加函数**

```python
# 追加到 huaqi_src/scheduler/jobs.py
from typing import Any

from huaqi_src.layers.data.raw_signal.models import RawSignalFilter
from huaqi_src.layers.data.raw_signal.store import RawSignalStore


def process_pending_signals_job(
    signal_store: RawSignalStore,
    pipeline: Any,
    user_id: str,
    batch_size: int = 50,
) -> None:
    pending = signal_store.query(
        RawSignalFilter(user_id=user_id, processed=0, limit=batch_size)
    )
    for signal in pending:
        try:
            pipeline.process(signal)
        except Exception:
            continue


def vectorize_pending_signals_job(
    signal_store: RawSignalStore,
    vector_adapter: Any,
    user_id: str,
    batch_size: int = 50,
) -> None:
    pending = signal_store.query(
        RawSignalFilter(user_id=user_id, vectorized=0, limit=batch_size)
    )
    for signal in pending:
        try:
            from huaqi_src.layers.data.memory.models import VectorDocument
            doc = VectorDocument(
                id=signal.id,
                user_id=signal.user_id,
                content=signal.content,
                metadata={"source_type": signal.source_type.value},
            )
            vector_adapter.upsert(doc)
            signal_store.mark_vectorized(signal.id)
        except Exception:
            continue
```

**Step 4：运行测试**

```bash
pytest tests/scheduler/ -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ tests/scheduler/ -x -q
```

---

### Task 4.3：Git 集成（TelosManager 自动 commit）

**背景：** `TelosManager.__init__` 中 `git_commit` 参数已存在但从未被使用（当前 `update()`/`create_custom()`/`archive()` 都不触发任何 git 操作）。

**Files:**
- Modify: `huaqi_src/layers/growth/telos/manager.py`（添加 `_git_auto_commit()` 私有方法，在 `update()` 后调用）
- Modify: `tests/unit/layers/growth/test_telos_manager.py`（新增测试）

**Step 1：写失败测试**

```python
# 追加到 tests/unit/layers/growth/test_telos_manager.py
import subprocess

def test_telos_manager_git_commit_on_update(tmp_path):
    """git_commit=True 时，维度更新后应自动执行 git commit"""
    telos_dir = tmp_path / "telos"

    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)

    manager = TelosManager(telos_dir=telos_dir, git_commit=True)
    manager.init()
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True)

    from huaqi_src.layers.growth.telos.models import HistoryEntry
    from datetime import datetime, timezone
    manager.update(
        "beliefs",
        new_content="选择比努力更重要",
        history_entry=HistoryEntry(
            version=1, change="更新信念", trigger="日记",
            confidence=0.7, updated_at=datetime.now(timezone.utc),
        ),
        confidence=0.7,
    )

    result = subprocess.run(
        ["git", "-C", str(tmp_path), "log", "--oneline", "-5"],
        capture_output=True, text=True,
    )
    assert "beliefs" in result.stdout
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/layers/growth/test_telos_manager.py::test_telos_manager_git_commit_on_update -v
```

**Step 3：添加 `_git_auto_commit` 方法**

```python
# huaqi_src/layers/growth/telos/manager.py
import subprocess

def _git_auto_commit(self, message: str) -> None:
    if not self._git_commit:
        return
    try:
        repo_root = self._dir.parent
        subprocess.run(["git", "-C", str(repo_root), "add", str(self._dir)],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo_root), "commit", "-m", message],
                       check=True, capture_output=True)
    except Exception:
        pass  # git 不可用时静默失败，不阻断主流程

def update(self, name: str, new_content: str, history_entry: HistoryEntry, confidence: float) -> None:
    dim = self.get(name)
    dim.content = new_content
    dim.confidence = confidence
    dim.update_count += 1
    dim.history.append(history_entry)
    self._path(name).write_text(dim.to_markdown(), encoding="utf-8")
    self._rebuild_index()
    self._git_auto_commit(f"telos: update {name} (v{dim.update_count})")
```

**Step 4：运行测试**

```bash
pytest tests/unit/layers/growth/test_telos_manager.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

## Phase 5：Agent 工作模式补全

> 实现对话写入 RAW_SIGNAL、通知机制、冷启动 CLI 入口。估时 2 小时。

### Task 5.1：对话结束后写入 RAW_SIGNAL

**背景：** 当前对话不会持久化到 RAW_SIGNAL，对话内容无法被后续信号提炼管道处理。

**Files:**
- Create: `huaqi_src/agent/hooks.py`
- Create: `tests/unit/agent/test_conversation_hook.py`

**Step 1：写失败测试**

```python
# tests/unit/agent/test_conversation_hook.py
from datetime import datetime, timezone
from pathlib import Path

from huaqi_src.agent.hooks import save_conversation_to_signal
from huaqi_src.layers.data.raw_signal.models import SourceType, RawSignalFilter
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter


def test_save_conversation_creates_raw_signal(tmp_path):
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    store = RawSignalStore(adapter=adapter)

    save_conversation_to_signal(
        user_id="u1",
        user_message="我最近很迷茫，不知道该做什么",
        assistant_message="听起来你在寻找方向感，能说说具体是什么让你感到迷茫吗？",
        signal_store=store,
        occurred_at=datetime.now(timezone.utc),
    )

    signals = store.query(RawSignalFilter(user_id="u1"))
    assert len(signals) == 1
    assert signals[0].source_type == SourceType.AI_CHAT
    assert "迷茫" in signals[0].content
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/agent/test_conversation_hook.py -v
```

**Step 3：实现 hooks.py**

```python
# huaqi_src/agent/hooks.py
from datetime import datetime, timezone
from typing import Optional

from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore


def save_conversation_to_signal(
    user_id: str,
    user_message: str,
    assistant_message: str,
    signal_store: RawSignalStore,
    occurred_at: Optional[datetime] = None,
) -> None:
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc)

    content = f"[用户] {user_message}\n[Huaqi] {assistant_message}"
    signal = RawSignal(
        user_id=user_id,
        source_type=SourceType.AI_CHAT,
        timestamp=occurred_at,
        content=content,
        metadata={"user_message": user_message, "assistant_message": assistant_message},
    )
    signal_store.save(signal)
```

**Step 4：运行测试**

```bash
pytest tests/unit/agent/test_conversation_hook.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

### Task 5.2：InterfaceAdapter ABC + CLINotifier

**Files:**
- Create: `huaqi_src/config/adapters/interface_base.py`
- Create: `huaqi_src/cli/notifier.py`
- Create: `tests/unit/config/test_interface_adapter.py`
- Create: `tests/unit/cli/test_notifier.py`

**Step 1：写失败测试**

```python
# tests/unit/config/test_interface_adapter.py
import pytest
from huaqi_src.config.adapters.interface_base import InterfaceAdapter


def test_interface_adapter_is_abstract():
    with pytest.raises(TypeError):
        InterfaceAdapter()


def test_interface_adapter_methods():
    methods = ["send_message", "send_question", "display_progress"]
    for m in methods:
        assert hasattr(InterfaceAdapter, m)
```

```python
# tests/unit/cli/test_notifier.py
from huaqi_src.cli.notifier import CLINotifier


def test_cli_notifier_send_message_outputs_text(capsys):
    notifier = CLINotifier(user_id="u1")
    notifier.send_message("你的 beliefs 维度刚刚更新了", user_id="u1")
    captured = capsys.readouterr()
    assert "beliefs" in captured.out


def test_cli_notifier_display_progress(capsys):
    notifier = CLINotifier(user_id="u1")
    notifier.display_progress("正在处理信号...")
    captured = capsys.readouterr()
    assert "处理" in captured.out
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/config/test_interface_adapter.py tests/unit/cli/test_notifier.py -v
```

**Step 3：实现**

```python
# huaqi_src/config/adapters/interface_base.py
from abc import ABC, abstractmethod
from typing import List, Optional


class InterfaceAdapter(ABC):

    @abstractmethod
    def send_message(self, text: str, user_id: str) -> None:
        pass

    @abstractmethod
    def send_question(self, text: str, user_id: str, options: Optional[List[str]] = None) -> None:
        pass

    @abstractmethod
    def display_progress(self, message: str) -> None:
        pass
```

```python
# huaqi_src/cli/notifier.py
from typing import List, Optional

from huaqi_src.config.adapters.interface_base import InterfaceAdapter


class CLINotifier(InterfaceAdapter):

    def __init__(self, user_id: str) -> None:
        self._user_id = user_id

    def send_message(self, text: str, user_id: str) -> None:
        print(f"\n{text}")

    def send_question(self, text: str, user_id: str, options: Optional[List[str]] = None) -> None:
        print(f"\n{text}")
        if options:
            for i, opt in enumerate(options, 1):
                print(f"  {i}. {opt}")

    def display_progress(self, message: str) -> None:
        print(f"{message}")
```

**Step 4：运行测试**

```bash
pytest tests/unit/config/test_interface_adapter.py tests/unit/cli/test_notifier.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

### Task 5.3：冷启动 CLI 入口（首次启动检测）

**背景：** 当前 `cli/chat.py` 没有检测是否首次启动，也不会自动跳转到 onboarding 问卷。

**Files:**
- Create: `huaqi_src/cli/commands/onboarding.py`
- Create: `tests/unit/cli/test_onboarding_command.py`

**Step 1：写失败测试**

```python
# tests/unit/cli/test_onboarding_command.py
from pathlib import Path
from huaqi_src.cli.commands.onboarding import is_first_run


def test_is_first_run_true_when_no_telos(tmp_path):
    assert is_first_run(telos_dir=tmp_path / "telos") is True


def test_is_first_run_false_when_telos_exists(tmp_path):
    telos_dir = tmp_path / "telos"
    telos_dir.mkdir()
    (telos_dir / "beliefs.md").touch()
    assert is_first_run(telos_dir=telos_dir) is False
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/cli/test_onboarding_command.py -v
```

**Step 3：实现**

```python
# huaqi_src/cli/commands/onboarding.py
from pathlib import Path


def is_first_run(telos_dir: Path) -> bool:
    if not telos_dir.exists():
        return True
    return len(list(telos_dir.glob("*.md"))) == 0
```

**Step 4：运行测试**

```bash
pytest tests/unit/cli/test_onboarding_command.py -v
```

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

## Phase 6：数据采集 Converters

> 实现 diary/wechat converter，完成 `converters/` 目录。估时 1.5 小时。

### Task 6.1：DiaryConverter（Markdown 日记 → RawSignal）

**Files:**
- Create: `huaqi_src/layers/data/raw_signal/converters/base.py`
- Create: `huaqi_src/layers/data/raw_signal/converters/diary.py`
- Create: `tests/unit/layers/data/converters/test_diary_converter.py`

**Step 1：写失败测试**

```python
# tests/unit/layers/data/converters/test_diary_converter.py
import pytest
from pathlib import Path
from datetime import datetime, timezone
from huaqi_src.layers.data.raw_signal.converters.diary import DiaryConverter
from huaqi_src.layers.data.raw_signal.models import SourceType


@pytest.fixture
def diary_file(tmp_path):
    content = """\
---
date: 2026-01-04
mood: 平静
tags:
  - 工作
  - 反思
---

今天思考了很多关于方向感的问题。
感觉需要重新审视自己的目标。
"""
    p = tmp_path / "2026-01-04.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_diary_converter_creates_raw_signal(diary_file):
    converter = DiaryConverter(user_id="u1")
    signals = converter.convert(diary_file)
    assert len(signals) == 1
    assert signals[0].source_type == SourceType.JOURNAL
    assert "方向感" in signals[0].content


def test_diary_converter_extracts_timestamp_from_frontmatter(diary_file):
    converter = DiaryConverter(user_id="u1")
    signals = converter.convert(diary_file)
    assert signals[0].timestamp.year == 2026
    assert signals[0].timestamp.month == 1
    assert signals[0].timestamp.day == 4


def test_diary_converter_extracts_metadata(diary_file):
    converter = DiaryConverter(user_id="u1")
    signals = converter.convert(diary_file)
    meta = signals[0].metadata
    assert meta["mood"] == "平静"
    assert "工作" in meta["tags"]


def test_diary_converter_empty_file_returns_empty(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    converter = DiaryConverter(user_id="u1")
    assert converter.convert(empty) == []


def test_diary_converter_no_frontmatter_uses_ingested_time(tmp_path):
    no_fm = tmp_path / "no_frontmatter.md"
    no_fm.write_text("今天是个好日子。", encoding="utf-8")
    converter = DiaryConverter(user_id="u1")
    signals = converter.convert(no_fm)
    assert len(signals) == 1
    diff = abs((signals[0].timestamp - datetime.now(timezone.utc)).total_seconds())
    assert diff < 5
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/layers/data/converters/test_diary_converter.py -v
```

**Step 3：实现 base.py 和 diary.py**

```python
# huaqi_src/layers/data/raw_signal/converters/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from huaqi_src.layers.data.raw_signal.models import RawSignal


class BaseConverter(ABC):

    def __init__(self, user_id: str) -> None:
        self._user_id = user_id

    @abstractmethod
    def convert(self, source: Path) -> List[RawSignal]:
        pass
```

```python
# huaqi_src/layers/data/raw_signal/converters/diary.py
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from huaqi_src.layers.data.raw_signal.converters.base import BaseConverter
from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType


def _parse_frontmatter(text: str):
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not match:
        return {}, text.strip()
    fm_text, body = match.group(1), match.group(2).strip()
    fm: Dict[str, Any] = {}
    for line in fm_text.splitlines():
        if ": " in line and not line.startswith("  "):
            key, _, val = line.partition(": ")
            fm[key.strip()] = val.strip()
        elif line.strip().startswith("- ") and fm:
            last_key = list(fm.keys())[-1]
            if not isinstance(fm[last_key], list):
                fm[last_key] = []
            fm[last_key].append(line.strip().lstrip("- "))
    return fm, body


class DiaryConverter(BaseConverter):

    def convert(self, source: Path) -> List[RawSignal]:
        text = source.read_text(encoding="utf-8").strip()
        if not text:
            return []

        fm, body = _parse_frontmatter(text)
        if not body:
            return []

        timestamp = datetime.now(timezone.utc)
        if "date" in fm:
            try:
                timestamp = datetime.strptime(str(fm["date"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        metadata: Dict[str, Any] = {}
        if "mood" in fm:
            metadata["mood"] = fm["mood"]
        if "tags" in fm:
            tags = fm["tags"]
            metadata["tags"] = tags if isinstance(tags, list) else [tags]

        return [
            RawSignal(
                user_id=self._user_id,
                source_type=SourceType.JOURNAL,
                timestamp=timestamp,
                content=body,
                metadata=metadata if metadata else None,
            )
        ]
```

**Step 4：运行测试**

```bash
pytest tests/unit/layers/data/converters/test_diary_converter.py -v
```

Expected: 5 passed

**Step 5：回归**

```bash
pytest tests/unit/ tests/integration/ -x -q
```

---

### Task 6.2：WechatConverter（微信导出文本 → RawSignal）

微信导出格式（`.txt`）：
```
2026-01-04 10:30:23 张三
你好啊！

2026-01-04 10:30:45 李四
你好！
```

**Files:**
- Create: `huaqi_src/layers/data/raw_signal/converters/wechat.py`
- Create: `tests/unit/layers/data/converters/test_wechat_converter.py`

**Step 1：写失败测试**

```python
# tests/unit/layers/data/converters/test_wechat_converter.py
import pytest
from pathlib import Path
from huaqi_src.layers.data.raw_signal.converters.wechat import WechatConverter
from huaqi_src.layers.data.raw_signal.models import SourceType

SAMPLE_WECHAT = """\
2026-01-04 10:30:23 张三
你好啊！

2026-01-04 10:30:45 李四
你好！我最近在思考人生方向。

2026-01-04 10:31:00 张三
哦，说来听听？
"""


@pytest.fixture
def wechat_file(tmp_path):
    p = tmp_path / "chat.txt"
    p.write_text(SAMPLE_WECHAT, encoding="utf-8")
    return p


def test_wechat_converter_each_message_is_one_signal(wechat_file):
    converter = WechatConverter(user_id="u1", participants=["张三", "李四"])
    signals = converter.convert(wechat_file)
    assert len(signals) == 3


def test_wechat_converter_source_type_is_wechat(wechat_file):
    converter = WechatConverter(user_id="u1", participants=["张三", "李四"])
    signals = converter.convert(wechat_file)
    assert all(s.source_type == SourceType.WECHAT for s in signals)


def test_wechat_converter_timestamp_from_message(wechat_file):
    converter = WechatConverter(user_id="u1", participants=["张三", "李四"])
    signals = converter.convert(wechat_file)
    assert signals[0].timestamp.hour == 10
    assert signals[0].timestamp.minute == 30


def test_wechat_converter_participants_in_metadata(wechat_file):
    converter = WechatConverter(user_id="u1", participants=["张三", "李四"], chat_name="朋友群")
    signals = converter.convert(wechat_file)
    meta = signals[0].metadata
    assert "张三" in meta["participants"] or "李四" in meta["participants"]
    assert meta["chat_name"] == "朋友群"
```

**Step 2：运行确认失败**

```bash
pytest tests/unit/layers/data/converters/test_wechat_converter.py -v
```

**Step 3：实现 wechat.py**

```python
# huaqi_src/layers/data/raw_signal/converters/wechat.py
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from huaqi_src.layers.data.raw_signal.converters.base import BaseConverter
from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

_MSG_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.+?)\n([\s\S]+?)(?=\n\d{4}-\d{2}-\d{2}|\Z)"
)


class WechatConverter(BaseConverter):

    def __init__(
        self,
        user_id: str,
        participants: Optional[List[str]] = None,
        chat_name: str = "",
    ) -> None:
        super().__init__(user_id)
        self._participants = participants or []
        self._chat_name = chat_name

    def convert(self, source: Path) -> List[RawSignal]:
        text = source.read_text(encoding="utf-8")
        signals = []

        for m in _MSG_PATTERN.finditer(text):
            ts_str, sender, content = m.group(1), m.group(2).strip(), m.group(3).strip()
            if not content:
                continue

            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            metadata = {
                "participants": self._participants or [sender],
                "chat_name": self._chat_name,
                "sender": sender,
            }

            signals.append(
                RawSignal(
                    user_id=self._user_id,
                    source_type=SourceType.WECHAT,
                    timestamp=ts,
                    content=f"{sender}：{content}",
                    metadata=metadata,
                )
            )

        return signals
```

**Step 4：运行测试**

```bash
pytest tests/unit/layers/data/converters/test_wechat_converter.py -v
```

Expected: 4 passed

**Step 5：完整回归**

```bash
pytest tests/unit/ tests/integration/ tests/scheduler/ -x -q
```

---

## 最终验证

所有 Phase 完成后执行：

**Step 1：ruff 零错误**

```bash
/Users/lianzimeng/Library/Python/3.9/bin/ruff check huaqi_src/layers/ huaqi_src/config/ huaqi_src/agent/ huaqi_src/scheduler/
```

Expected: `All checks passed!`

**Step 2：全量测试**

```bash
pytest tests/unit/ tests/integration/ tests/scheduler/ -q --tb=short
```

Expected: 250+ passed, 0 failed

**Step 3：对照验收清单**

| 验收项 | Phase | 关键文件 |
|-------|-------|---------|
| ruff 零错误 | Phase 1 | `config/errors.py` + `layers/` |
| `__init__.py` 公开接口 | Phase 1 | 各模块 `__init__.py` |
| Step2 时间窗口过滤 | Phase 2 | `raw_signal/pipeline.py` |
| 强信号绕过阈值 | Phase 2 | `raw_signal/pipeline.py` |
| INDEX.md 含内容摘要 | Phase 2 | `telos/manager.py:_rebuild_index` |
| archive/create_custom 自动记录 META | Phase 2 | `telos/manager.py` |
| 用户纠错下调 confidence | Phase 2 | `telos/meta.py:add_correction` |
| 多用户 UserProfile/UserContext | Phase 3 | `config/users.py` |
| VectorAdapter ABC | Phase 3 | `config/adapters/vector_base.py` |
| SchedulerAdapter + APScheduler | Phase 4 | `config/adapters/scheduler_base.py` |
| 积压信号定时处理 + 向量化 | Phase 4 | `scheduler/jobs.py` |
| Git auto-commit | Phase 4 | `telos/manager.py:_git_auto_commit` |
| 对话写入 RAW_SIGNAL | Phase 5 | `agent/hooks.py` |
| InterfaceAdapter + CLINotifier | Phase 5 | `config/adapters/interface_base.py` + `cli/notifier.py` |
| 首次启动检测 | Phase 5 | `cli/commands/onboarding.py` |
| DiaryConverter | Phase 6 | `raw_signal/converters/diary.py` |
| WechatConverter | Phase 6 | `raw_signal/converters/wechat.py` |

---

**文档版本**：v1.1
**创建时间**：2026-01-04
**对应验收清单**：`docs/designs/2026-01-04-acceptance-checklist.md`
**TDD 策略**：`docs/designs/2026-01-04-test-strategy.md`
