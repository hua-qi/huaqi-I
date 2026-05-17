# Plan: telos-distillation-scheduling

**Goal:** 修复 TELOS 蒸馏的自动触发机制：补 pytest-asyncio 依赖，提供 CLI 蒸馏命令，使其可在 GitHub Actions 中定时执行。

**Architecture:** 3 个 Task：依赖修复 → CLI 命令 + 蒸馏逻辑 → GitHub Actions 工作流。每步独立可测可提交。

**Spec:** `docs/specs/telos-distillation-scheduling.md`

---

## 背景阅读

实施前必读：
- `huaqi_src/layers/data/raw_signal/pipeline.py` — `DistillationPipeline`（异步 process 方法）
- `huaqi_src/layers/data/raw_signal/store.py` — `RawSignalStore`
- `huaqi_src/layers/data/raw_signal/models.py` — `RawSignalFilter` 的 `processed` 字段
- `huaqi_src/layers/growth/telos/engine.py` — `TelosEngine`
- `huaqi_src/cli/__init__.py` — CLI 子命令注册模式
- `huaqi_src/cli/commands/scheduler.py` — 参考 CLI 命令结构
- `.github/workflows/daily-report.yml` — 参考 GitHub Actions 工作流模板

运行已有测试确认基线：
```bash
pytest tests/ -x -m "not e2e" --tb=short
```

---

## Task 1: 补 pytest-asyncio 依赖

**影响**: `pyproject.toml` 一行改动，修复 15 个异步测试假失败。

**Files:**
- Modify: `pyproject.toml`

### Step 1: 写失败测试

无需新测试。现有 15 个测试已处于失败状态：
- `tests/unit/layers/growth/test_telos_engine.py` — 3 个 `TestStep345Combined` 测试
- `tests/unit/layers/data/test_raw_signal_pipeline.py` — 7 个异步测试
- `tests/unit/layers/data/test_work_signal_ingester.py` — 5 个异步测试

### Step 2: 运行确认失败

```bash
pytest tests/unit/layers/growth/test_telos_engine.py tests/unit/layers/data/ -v 2>&1 | grep "async def functions are not natively supported"
```

期望：15 条 "async def functions are not natively supported" 错误。

### Step 3: 写实现

在 `pyproject.toml` 的 `[project.optional-dependencies] dev` 列表末尾追加 `"pytest-asyncio>=0.24.0"`。

### Step 4: 运行确认通过

```bash
pip install -e ".[dev]" --break-system-packages
pytest tests/unit/layers/growth/test_telos_engine.py tests/unit/layers/data/ -v
```

期望：全部 PASSED，无 async 相关错误。

### Step 5: 冒烟测试沉淀

此 Task 无新增功能，不追加冒烟测试。运行现有冒烟测试确认无回归：
```bash
pytest tests/smoke_test.py -v
```

---

## Task 2: CLI 蒸馏命令 + 蒸馏逻辑

**背景**: 需要一个新的 CLI 命令 `huaqi telos distill`，它能连接 `RawSignalStore`，捞取 `processed=0` 的信号，送入 `DistillationPipeline.process()`，然后标记为已处理。`DistillationPipeline.process()` 是 `async def`，CLI 中需要用 `asyncio.run()` 包装。

**Files:**
- Create: `huaqi_src/cli/commands/telos.py` — CLI 命令
- Create: `huaqi_src/layers/capabilities/telos_distiller.py` — 蒸馏逻辑（不含 CLI 粘合代码）
- Modify: `huaqi_src/cli/__init__.py` — 注册 telos_app
- Test: `tests/unit/layers/capabilities/test_telos_distiller.py` — 新建单元测试

### Step 1: 写失败测试

创建 `tests/unit/layers/capabilities/test_telos_distiller.py`：

```python
"""Unit tests for telos_distiller module."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from datetime import datetime, timezone


class TestRunDistillation:
    def test_returns_zero_when_no_unprocessed(self, tmp_path):
        """AC-5: 无未处理信号时返回 processed=0，不报错。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation

        mock_store = MagicMock()
        mock_store.query.return_value = []

        with patch(
            "huaqi_src.layers.capabilities.telos_distiller._get_signal_store",
            return_value=mock_store,
        ):
            result = run_distillation(limit=10, user_id="test_user")

        assert result["processed"] == 0
        assert result["errors"] == 0

    def test_processes_unprocessed_signals(self, tmp_path):
        """AC-4: 查询 processed=0 的信号并逐条送入 pipeline。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        signal1 = RawSignal(
            user_id="test_user",
            source_type=SourceType.AI_CHAT,
            timestamp=datetime.now(timezone.utc),
            content="测试信号1",
        )
        signal2 = RawSignal(
            user_id="test_user",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="测试信号2",
        )

        mock_store = MagicMock()
        mock_store.query.return_value = [signal1, signal2]

        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(return_value={"signal_id": "s1"})

        with patch(
            "huaqi_src.layers.capabilities.telos_distiller._get_signal_store",
            return_value=mock_store,
        ):
            with patch(
                "huaqi_src.layers.capabilities.telos_distiller._get_pipeline",
                return_value=mock_pipeline,
            ):
                result = run_distillation(limit=10, user_id="test_user")

        assert result["processed"] == 2
        assert result["errors"] == 0
        assert mock_pipeline.process.call_count == 2

    def test_error_isolation(self, tmp_path):
        """AC-6: 单条蒸馏失败不影响其余信号。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        signal1 = RawSignal(
            user_id="test_user",
            source_type=SourceType.AI_CHAT,
            timestamp=datetime.now(timezone.utc),
            content="正常信号",
        )
        signal2 = RawSignal(
            user_id="test_user",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="会失败的信号",
        )

        mock_store = MagicMock()
        mock_store.query.return_value = [signal1, signal2]

        mock_pipeline = MagicMock()
        async def side_effect(signal):
            if "失败" in signal.content:
                raise RuntimeError("模拟失败")
            return {"signal_id": signal.id}
        mock_pipeline.process = AsyncMock(side_effect=side_effect)

        with patch(
            "huaqi_src.layers.capabilities.telos_distiller._get_signal_store",
            return_value=mock_store,
        ):
            with patch(
                "huaqi_src.layers.capabilities.telos_distiller._get_pipeline",
                return_value=mock_pipeline,
            ):
                result = run_distillation(limit=10, user_id="test_user")

        assert result["processed"] == 1
        assert result["errors"] == 1

    def test_signals_marked_processed_after_distillation(self, tmp_path):
        """AC-7: 蒸馏完成后信号被标记为 processed=1。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        signal = RawSignal(
            user_id="test_user",
            source_type=SourceType.AI_CHAT,
            timestamp=datetime.now(timezone.utc),
            content="测试信号",
        )

        mock_store = MagicMock()
        mock_store.query.return_value = [signal]

        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(return_value={"signal_id": signal.id})

        with patch(
            "huaqi_src.layers.capabilities.telos_distiller._get_signal_store",
            return_value=mock_store,
        ):
            with patch(
                "huaqi_src.layers.capabilities.telos_distiller._get_pipeline",
                return_value=mock_pipeline,
            ):
                run_distillation(limit=10, user_id="test_user")

        mock_store.mark_processed.assert_called_once_with(signal.id)
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/layers/capabilities/test_telos_distiller.py -v
```

期望：`ModuleNotFoundError: No module named 'huaqi_src.layers.capabilities.telos_distiller'`

### Step 3: 写实现

**3a.** 创建 `huaqi_src/layers/capabilities/telos_distiller.py`：

```python
import asyncio
import logging
from typing import Any, Dict

from huaqi_src.layers.data.raw_signal.models import RawSignalFilter

logger = logging.getLogger(__name__)


def _get_signal_store():
    from huaqi_src.config.paths import get_db_path
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    return RawSignalStore(adapter=SQLiteStorageAdapter(db_path=get_db_path()))


def _get_pipeline():
    from huaqi_src.config.paths import get_telos_dir
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
    from huaqi_src.layers.growth.telos.engine import TelosEngine
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.growth_events import GrowthEventStore
    from huaqi_src.config.paths import get_db_path

    adapter = SQLiteStorageAdapter(db_path=get_db_path())
    signal_store = RawSignalStore(adapter=adapter)
    event_store = GrowthEventStore(adapter=adapter)

    telos_dir = get_telos_dir()
    telos_mgr = TelosManager(telos_dir=telos_dir, git_commit=True)

    from huaqi_src.cli.context import build_llm_manager
    llm_mgr = build_llm_manager(temperature=0.3, max_tokens=2000)
    if llm_mgr is None:
        raise RuntimeError("未配置 LLM，无法运行蒸馏任务")

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


async def _run_async(limit: int, user_id: str) -> Dict[str, Any]:
    store = _get_signal_store()
    pipeline = _get_pipeline()

    unprocessed = store.query(
        RawSignalFilter(user_id=user_id, processed=0, limit=limit)
    )
    if not unprocessed:
        return {"processed": 0, "errors": 0}

    processed = 0
    errors = 0
    for signal in unprocessed:
        try:
            await pipeline.process(signal)
            store.mark_processed(signal.id)
            processed += 1
        except Exception as e:
            errors += 1
            logger.error(f"蒸馏失败 signal={signal.id}: {e}")

    return {"processed": processed, "errors": errors}


def run_distillation(limit: int = 10, user_id: str = "default") -> Dict[str, Any]:
    return asyncio.run(_run_async(limit=limit, user_id=user_id))
```

**3b.** 创建 `huaqi_src/cli/commands/telos.py`：

```python
"""TELOS 成长引擎 CLI 命令。"""
import typer

telos_app = typer.Typer(name="telos", help="TELOS 成长引擎管理")


@telos_app.command("distill")
def distill_command(
    limit: int = typer.Option(10, "--limit", "-l", help="每次最多处理的信号数"),
):
    """运行信号蒸馏——捞取未处理信号，提炼 TELOS 维度认知。"""
    from huaqi_src.cli.context import ensure_initialized
    from huaqi_src.layers.capabilities.telos_distiller import run_distillation

    ensure_initialized()

    print(f"开始蒸馏（上限 {limit} 条）...")
    result = run_distillation(limit=limit)
    print(f"完成：处理 {result['processed']} 条，失败 {result['errors']} 条")
```

**3c.** 在 `huaqi_src/cli/__init__.py` 中注册：

```python
# 在 import 区域追加
from huaqi_src.cli.commands.telos import telos_app

# 在 app.add_typer 区域追加
app.add_typer(telos_app, name="telos", rich_help_panel="操作工具")
```

### Step 4: 运行确认通过

```bash
pytest tests/unit/layers/capabilities/test_telos_distiller.py -v
```

期望：全部 PASSED。

### Step 5: 冒烟测试沉淀

在 `tests/smoke_test.py` 末尾的 `Feature Acceptance Tests` 区域追加：

```python
class TestTelosDistillationScheduling:
    """telos-distillation-scheduling 功能验收。

    Spec: docs/specs/telos-distillation-scheduling.md
    """

    def test_dep_asyncio_in_dev(self):
        """AC-1: pytest-asyncio 在 dev 依赖中。"""
        import tomllib
        from pathlib import Path

        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        dev_deps = data["project"]["optional-dependencies"]["dev"]
        assert any("pytest-asyncio" in d for d in dev_deps)

    def test_distillation_entry_exists(self):
        """AC-3: 蒸馏入口模块存在。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation
        assert callable(run_distillation)

    def test_distillation_no_unprocessed(self, data_dir, set_data_dir):
        """AC-5: 无未处理信号时正常返回。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation
        result = run_distillation(limit=10, user_id="smoke_test_user")
        assert result["processed"] == 0
        assert "errors" in result

    def test_cli_telos_app_registered(self):
        """AC-3: huaqi telos CLI 命令已注册。"""
        from huaqi_src.cli import app
        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, ["telos", "--help"])
        assert result.exit_code == 0
        assert "distill" in result.stdout
```

```bash
pytest tests/smoke_test.py -v -k "TestTelosDistillationScheduling"
```

---

## Task 3: GitHub Actions 工作流

**背景**: 在用户数据仓库（`huaqi`）中创建定时工作流，调用 `huaqi telos distill`。参照已有模式（`daily-report.yml`：checkout 数据仓库 + checkout 源码 + `pip install` + 运行 CLI 命令 + commit 回数据仓库）。

**注意**: 蒸馏会修改 TELOS 维度文件（`telos/*.md`），这些修改由 `TelosManager` 内部的 `_git_auto_commit` 处理（在数据仓库内）。但工作流层面仍需 commit/push 以确保变更同步到远端。

**Files:**
- Create: `/Users/lianzimeng/workspace/huaqi/.github/workflows/telos-distill.yml`
- Test: `tests/smoke_test.py`（追加验证工作流文件存在）

### Step 1: 写失败测试

在 `tests/smoke_test.py` 的 `TestTelosDistillationScheduling` 类中追加：

```python
    def test_github_workflow_exists(self):
        """AC-3: GitHub Actions 工作流文件存在。"""
        from pathlib import Path
        workflow_path = Path(__file__).parent.parent / ".." / ".." / ".github" / "workflows" / "telos-distill.yml"
        # 工作流在数据仓库中，不在源码仓库。确认源码仓库中的引用即可。
        # 此测试只验证本仓库中功能模块存在。
        pass  # 工作流文件在 huaqi 数据仓库中，不在本仓库，此处为占位
```

工作流文件在 `huaqi` 数据仓库中（非 `huaqi-growing` 源码仓库），无法在源码仓库的单元测试中直接断言。冒烟测试中此项为占位，实际验收需手动检查工作流运行成功。

### Step 2: 创建 GitHub Actions 工作流

创建 `/Users/lianzimeng/workspace/huaqi/.github/workflows/telos-distill.yml`：

```yaml
name: TELOS 信号蒸馏

on:
  schedule:
    - cron: '7 */4 * * *'   # 每 4 小时执行一次（UTC 分钟避开整点）
  workflow_dispatch:

jobs:
  distill:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main

      - uses: actions/checkout@v4
        with:
          repository: hua-qi/huaqi-I
          path: huaqi-src

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install huaqi
        run: pip install -e huaqi-src/

      - name: Run TELOS distillation
        id: distill
        env:
          HUAQI_DATA_DIR: ${{ github.workspace }}
          HUAQI_SKIP_RECOVERY: '1'
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          huaqi telos distill --limit 10

      - name: Commit and push
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git fetch origin main && git checkout main && git reset --hard origin/main
          git config user.name "Huaqi Bot"
          git config user.email "bot@huaqi.local"
          git add telos/ 2>/dev/null || true
          git add .
          if git diff --cached --quiet; then
            echo "No changes to commit"
          else
            git commit -m "chore: telos distillation $(date +%F-%H%M)"
            git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
            git push
          fi
```

### Step 3: 运行确认

无法在本地自动验证 GitHub Actions 工作流。通过以下手动确认：
1. 在 `huaqi` 数据仓库中 `git push` 该工作流文件
2. 在 GitHub Actions 页面手动触发 `workflow_dispatch`
3. 确认任务执行成功，telos 维度文件被正确更新

---

## 快速参考

### 任务依赖

```
Task 1 (pytest-asyncio) → 独立可做
Task 2 (CLI + 蒸馏逻辑) → 独立可做
Task 3 (GitHub Actions) → 依赖 Task 2（需要 CLI 命令存在）
```

### 关键文件

| 做什么 | 文件 |
|--------|------|
| 补依赖 | `pyproject.toml` |
| 蒸馏逻辑 | `huaqi_src/layers/capabilities/telos_distiller.py`（新建）|
| CLI 命令 | `huaqi_src/cli/commands/telos.py`（新建）|
| CLI 注册 | `huaqi_src/cli/__init__.py` |
| 单元测试 | `tests/unit/layers/capabilities/test_telos_distiller.py`（新建）|
| 冒烟测试 | `tests/smoke_test.py` |
| GitHub Actions | `huaqi/.github/workflows/telos-distill.yml`（新建，数据仓库）|
