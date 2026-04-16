# 工作习惯分析与 Codeflicker 个性化注入 Implementation Plan

**Goal:** 分析用户工作习惯并将结论自动注入 `~/.codeflicker/AGENTS.md`，使 codeflicker 在所有项目中感知用户的技术决策倾向与风格。

**Architecture:** 新增 `WorkDataSource` 注册表（三个实现）+ `WorkSignalIngester`，在 `CLIChatWatcher` 处理完会话后触发信号摄入，信号流经已有 `DistillationPipeline` → `TelosEngine` 更新 `work_style` 自定义维度；再由 `CLAUDEmdWriter` 监听维度变化后重写 `~/.codeflicker/AGENTS.md` 中的 `## My Work Style` 段落。阶段 2 补全 `DistillationPipeline` 消费 `new_dimension_hint` 的逻辑。

**Tech Stack:** Python 3.12, Pydantic v2, pytest-asyncio, pathlib, abc, 现有 `DistillationPipeline` / `TelosManager` / `RawSignal` 体系

---

## 阶段 1：数据源层

### Task 1: 扩展 SourceType 枚举

**Files:**
- Modify: `huaqi_src/layers/data/raw_signal/models.py:17-27`
- Test: `tests/unit/layers/data/test_raw_signal_models.py`

**Step 1: 写失败测试**

在 `tests/unit/layers/data/test_raw_signal_models.py` 追加：

```python
def test_source_type_has_work_doc():
    from huaqi_src.layers.data.raw_signal.models import SourceType
    assert SourceType.WORK_DOC == "work_doc"
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/data/test_raw_signal_models.py::test_source_type_has_work_doc -v
```

预期：`FAILED` — `AttributeError: 'WORK_DOC' is not a valid SourceType`

**Step 3: 最小实现**

在 `models.py` 的 `SourceType` 类末尾添加：

```python
WORK_DOC = "work_doc"
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/data/test_raw_signal_models.py::test_source_type_has_work_doc -v
```

预期：`PASSED`

**Step 5: 提交**

```
git add huaqi_src/layers/data/raw_signal/models.py tests/unit/layers/data/test_raw_signal_models.py
git commit -m "feat: add SourceType.WORK_DOC"
```

---

### Task 2: WorkDataSource 抽象基类与注册表

**Files:**
- Create: `huaqi_src/layers/data/collectors/work_data_source.py`
- Create: `tests/unit/layers/data/test_work_data_source.py`

**Step 1: 写失败测试**

```python
# tests/unit/layers/data/test_work_data_source.py
from unittest.mock import MagicMock
from huaqi_src.layers.data.collectors.work_data_source import (
    WorkDataSource,
    register_work_source,
    get_work_sources,
    _work_source_registry,
)


def test_register_and_get():
    _work_source_registry.clear()
    source = MagicMock(spec=WorkDataSource)
    register_work_source(source)
    assert source in get_work_sources()


def test_get_returns_copy():
    _work_source_registry.clear()
    source = MagicMock(spec=WorkDataSource)
    register_work_source(source)
    result = get_work_sources()
    result.clear()
    assert len(get_work_sources()) == 1
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/data/test_work_data_source.py -v
```

预期：`FAILED` — `ModuleNotFoundError`

**Step 3: 最小实现**

```python
# huaqi_src/layers/data/collectors/work_data_source.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional


class WorkDataSource(ABC):
    name: str
    source_type: str

    @abstractmethod
    def fetch_documents(self, since: Optional[datetime] = None) -> List[str]:
        pass


_work_source_registry: list = []


def register_work_source(source: WorkDataSource) -> None:
    _work_source_registry.append(source)


def get_work_sources() -> list:
    return list(_work_source_registry)
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/data/test_work_data_source.py -v
```

预期：`PASSED`

**Step 5: 提交**

```
git add huaqi_src/layers/data/collectors/work_data_source.py tests/unit/layers/data/test_work_data_source.py
git commit -m "feat: add WorkDataSource base class and registry"
```

---

### Task 3: CodeflickerSource 实现

从 `get_cli_chats_dir()` 下读取 codeflicker 的 `.md` 文件，支持 `since` 增量过滤。

**Files:**
- Create: `huaqi_src/layers/data/collectors/work_sources/__init__.py`
- Create: `huaqi_src/layers/data/collectors/work_sources/codeflicker.py`
- Create: `tests/unit/layers/data/test_work_sources.py`

**Step 1: 写失败测试**

```python
# tests/unit/layers/data/test_work_sources.py
import datetime
from pathlib import Path
from huaqi_src.layers.data.collectors.work_sources.codeflicker import CodeflickerSource


def test_fetch_documents_returns_file_contents(tmp_path):
    chats_dir = tmp_path / "memory" / "cli_chats"
    chats_dir.mkdir(parents=True)
    (chats_dir / "session1.md").write_text("内容A")
    (chats_dir / "session2.md").write_text("内容B")

    source = CodeflickerSource(cli_chats_dir=chats_dir)
    docs = source.fetch_documents()
    assert len(docs) == 2
    assert "内容A" in docs or "内容B" in docs


def test_fetch_documents_filters_by_since(tmp_path):
    chats_dir = tmp_path / "cli_chats"
    chats_dir.mkdir(parents=True)
    old_file = chats_dir / "old.md"
    new_file = chats_dir / "new.md"
    old_file.write_text("旧内容")
    new_file.write_text("新内容")

    cutoff = datetime.datetime.now() + datetime.timedelta(seconds=1)
    import time; time.sleep(0.05)
    new_file.touch()

    source = CodeflickerSource(cli_chats_dir=chats_dir)
    docs = source.fetch_documents(since=cutoff)
    assert docs == ["新内容"]
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/data/test_work_sources.py::test_fetch_documents_returns_file_contents -v
```

预期：`FAILED` — `ModuleNotFoundError`

**Step 3: 最小实现**

```python
# huaqi_src/layers/data/collectors/work_sources/__init__.py
# (空文件)
```

```python
# huaqi_src/layers/data/collectors/work_sources/codeflicker.py
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from huaqi_src.layers.data.collectors.work_data_source import WorkDataSource


class CodeflickerSource(WorkDataSource):
    name = "codeflicker"
    source_type = "codeflicker_chat"

    def __init__(self, cli_chats_dir: Optional[Path] = None) -> None:
        if cli_chats_dir is None:
            from huaqi_src.config.paths import get_cli_chats_dir
            cli_chats_dir = get_cli_chats_dir()
        self._dir = Path(cli_chats_dir)

    def fetch_documents(self, since: Optional[datetime] = None) -> List[str]:
        if not self._dir.exists():
            return []
        docs = []
        for f in sorted(self._dir.rglob("*.md")):
            if since is not None:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime <= since:
                    continue
            try:
                docs.append(f.read_text(encoding="utf-8"))
            except OSError:
                pass
        return docs
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/data/test_work_sources.py -v
```

预期：`PASSED`

**Step 5: 提交**

```
git add huaqi_src/layers/data/collectors/work_sources/ tests/unit/layers/data/test_work_sources.py
git commit -m "feat: add CodeflickerSource work data source"
```

---

### Task 4: HuaqiDocsSource 实现

读取 `huaqi-growing/docs/` 目录下所有 `.md` 文件。

**Files:**
- Create: `huaqi_src/layers/data/collectors/work_sources/huaqi_docs.py`
- Modify: `tests/unit/layers/data/test_work_sources.py`

**Step 1: 写失败测试**

在 `tests/unit/layers/data/test_work_sources.py` 追加：

```python
def test_huaqi_docs_source_reads_md_files(tmp_path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "designs").mkdir(parents=True)
    (docs_dir / "designs" / "design1.md").write_text("设计文档内容")

    from huaqi_src.layers.data.collectors.work_sources.huaqi_docs import HuaqiDocsSource
    source = HuaqiDocsSource(docs_dir=docs_dir)
    docs = source.fetch_documents()
    assert "设计文档内容" in docs
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/data/test_work_sources.py::test_huaqi_docs_source_reads_md_files -v
```

预期：`FAILED` — `ModuleNotFoundError`

**Step 3: 最小实现**

```python
# huaqi_src/layers/data/collectors/work_sources/huaqi_docs.py
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from huaqi_src.layers.data.collectors.work_data_source import WorkDataSource


class HuaqiDocsSource(WorkDataSource):
    name = "huaqi_docs"
    source_type = "huaqi_docs"

    def __init__(self, docs_dir: Optional[Path] = None) -> None:
        if docs_dir is None:
            docs_dir = Path(__file__).parents[5] / "docs"
        self._dir = Path(docs_dir)

    def fetch_documents(self, since: Optional[datetime] = None) -> List[str]:
        if not self._dir.exists():
            return []
        docs = []
        for f in sorted(self._dir.rglob("*.md")):
            if since is not None:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime <= since:
                    continue
            try:
                docs.append(f.read_text(encoding="utf-8"))
            except OSError:
                pass
        return docs
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/data/test_work_sources.py -v
```

预期：全部 `PASSED`

**Step 5: 提交**

```
git add huaqi_src/layers/data/collectors/work_sources/huaqi_docs.py tests/unit/layers/data/test_work_sources.py
git commit -m "feat: add HuaqiDocsSource work data source"
```

---

### Task 5: KuaishouDocsSource 实现（占位，可替换）

公司内部文档系统 HTTP API 接入，当前以占位实现交付。

**Files:**
- Create: `huaqi_src/layers/data/collectors/work_sources/kuaishou_docs.py`
- Modify: `tests/unit/layers/data/test_work_sources.py`

**Step 1: 写失败测试**

在 `tests/unit/layers/data/test_work_sources.py` 追加：

```python
def test_kuaishou_docs_source_returns_list():
    from huaqi_src.layers.data.collectors.work_sources.kuaishou_docs import KuaishouDocsSource
    source = KuaishouDocsSource()
    docs = source.fetch_documents()
    assert isinstance(docs, list)
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/data/test_work_sources.py::test_kuaishou_docs_source_returns_list -v
```

预期：`FAILED` — `ModuleNotFoundError`

**Step 3: 最小实现**

```python
# huaqi_src/layers/data/collectors/work_sources/kuaishou_docs.py
from datetime import datetime
from typing import List, Optional

from huaqi_src.layers.data.collectors.work_data_source import WorkDataSource


class KuaishouDocsSource(WorkDataSource):
    name = "kuaishou_docs"
    source_type = "kuaishou_docs"

    def fetch_documents(self, since: Optional[datetime] = None) -> List[str]:
        return []
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/data/test_work_sources.py -v
```

预期：全部 `PASSED`

**Step 5: 提交**

```
git add huaqi_src/layers/data/collectors/work_sources/kuaishou_docs.py tests/unit/layers/data/test_work_sources.py
git commit -m "feat: add KuaishouDocsSource (stub)"
```

---

## 阶段 2：信号摄入层

### Task 6: WorkSignalIngester

从所有注册 `WorkDataSource` 拉取文档，包装为 `RawSignal(source_type=WORK_DOC)` 并注入 `DistillationPipeline`；首次运行时自动创建 `work_style` 维度。

**Files:**
- Create: `huaqi_src/layers/data/collectors/work_signal_ingester.py`
- Create: `tests/unit/layers/data/test_work_signal_ingester.py`

**Step 1: 写失败测试**

```python
# tests/unit/layers/data/test_work_signal_ingester.py
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from huaqi_src.layers.data.collectors.work_signal_ingester import WorkSignalIngester
from huaqi_src.layers.data.collectors.work_data_source import (
    _work_source_registry,
    register_work_source,
)


@pytest.fixture(autouse=True)
def clear_registry():
    _work_source_registry.clear()
    yield
    _work_source_registry.clear()


@pytest.fixture
def mock_pipeline():
    p = MagicMock()
    p.process = AsyncMock(return_value={})
    return p


@pytest.fixture
def mock_telos_manager():
    from huaqi_src.config.errors import DimensionNotFoundError
    mgr = MagicMock()
    mgr.get.side_effect = DimensionNotFoundError("not found")
    return mgr


@pytest.fixture
def mock_signal_store():
    return MagicMock()


async def test_ingest_calls_pipeline_for_each_doc(
    mock_pipeline, mock_telos_manager, mock_signal_store
):
    source = MagicMock()
    source.name = "test_source"
    source.fetch_documents.return_value = ["文档1", "文档2"]
    register_work_source(source)

    mock_telos_manager.get.side_effect = None
    mock_telos_manager.get.return_value = MagicMock()

    ingester = WorkSignalIngester(
        signal_store=mock_signal_store,
        pipeline=mock_pipeline,
        telos_manager=mock_telos_manager,
        user_id="user1",
    )
    count = await ingester.ingest()
    assert count == 2
    assert mock_pipeline.process.call_count == 2


async def test_ingest_creates_work_style_dimension_if_missing(
    mock_pipeline, mock_telos_manager, mock_signal_store
):
    source = MagicMock()
    source.name = "s"
    source.fetch_documents.return_value = []
    register_work_source(source)

    ingester = WorkSignalIngester(
        signal_store=mock_signal_store,
        pipeline=mock_pipeline,
        telos_manager=mock_telos_manager,
        user_id="user1",
    )
    await ingester.ingest()
    mock_telos_manager.create_custom.assert_called_once()


async def test_ingest_does_not_recreate_existing_work_style(
    mock_pipeline, mock_telos_manager, mock_signal_store
):
    source = MagicMock()
    source.name = "s"
    source.fetch_documents.return_value = []
    register_work_source(source)

    mock_telos_manager.get.side_effect = None
    mock_telos_manager.get.return_value = MagicMock()

    ingester = WorkSignalIngester(
        signal_store=mock_signal_store,
        pipeline=mock_pipeline,
        telos_manager=mock_telos_manager,
        user_id="user1",
    )
    await ingester.ingest()
    mock_telos_manager.create_custom.assert_not_called()
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/data/test_work_signal_ingester.py -v
```

预期：`FAILED` — `ModuleNotFoundError`

**Step 3: 最小实现**

```python
# huaqi_src/layers/data/collectors/work_signal_ingester.py
from datetime import datetime, timezone
from typing import Optional

from huaqi_src.config.errors import DimensionNotFoundError
from huaqi_src.layers.data.collectors.work_data_source import get_work_sources
from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import DimensionLayer


class WorkSignalIngester:

    def __init__(
        self,
        signal_store: RawSignalStore,
        pipeline: DistillationPipeline,
        telos_manager: TelosManager,
        user_id: str,
    ) -> None:
        self._store = signal_store
        self._pipeline = pipeline
        self._mgr = telos_manager
        self._user_id = user_id

    async def ingest(self, since: Optional[datetime] = None) -> int:
        self._ensure_work_style_dimension()
        count = 0
        for source in get_work_sources():
            docs = source.fetch_documents(since=since)
            for doc in docs:
                signal = RawSignal(
                    user_id=self._user_id,
                    source_type=SourceType.WORK_DOC,
                    timestamp=datetime.now(timezone.utc),
                    content=doc,
                    metadata={"work_source": source.name},
                )
                self._store.save(signal)
                await self._pipeline.process(signal)
                count += 1
        return count

    def _ensure_work_style_dimension(self) -> None:
        try:
            self._mgr.get("work_style")
        except DimensionNotFoundError:
            self._mgr.create_custom(
                name="work_style",
                layer=DimensionLayer.MIDDLE,
                initial_content="（待积累）",
            )
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/data/test_work_signal_ingester.py -v
```

预期：全部 `PASSED`

**Step 5: 提交**

```
git add huaqi_src/layers/data/collectors/work_signal_ingester.py tests/unit/layers/data/test_work_signal_ingester.py
git commit -m "feat: add WorkSignalIngester"
```

---

### Task 7: 接入 CLIChatWatcher

在 `_process_codeflicker_session` 末尾调用 `WorkSignalIngester.ingest()`。

**Files:**
- Modify: `huaqi_src/layers/data/collectors/cli_chat_watcher.py`
- Modify: `tests/unit/layers/data/test_work_signal_ingester.py`（追加集成验证测试）

**背景说明：** `_process_codeflicker_session` 目前在 WorkLogWriter 调用后就返回。新增一个可选的 `work_signal_ingester` 参数，调用时若已注入则触发 `ingest()`。

**Step 1: 写失败测试**

在 `tests/unit/layers/data/test_work_signal_ingester.py` 追加：

```python
async def test_cli_chat_watcher_calls_ingester_after_work_log(tmp_path):
    from huaqi_src.layers.data.collectors.cli_chat_watcher import CLIChatWatcher
    from huaqi_src.layers.data.collectors.cli_chat_parser import CLIChatMessage, CLIChatSession

    mock_ingester = MagicMock()
    mock_ingester.ingest = AsyncMock(return_value=0)

    watcher = CLIChatWatcher(data_dir=tmp_path, work_signal_ingester=mock_ingester)

    session = CLIChatSession(
        session_id="sess1",
        messages=[CLIChatMessage(role="user", content="测试消息", timestamp=None)],
        time_start="2026-11-04T10:00:00Z",
        time_end="2026-11-04T10:30:00Z",
        project_dir="/some/project",
        git_branch="main",
    )
    fake_file = tmp_path / "session.jsonl"
    fake_file.touch()

    watcher._process_codeflicker_session(session, fake_file)
    mock_ingester.ingest.assert_called_once()
```

> 注意：`_process_codeflicker_session` 是同步方法，调用异步 `ingest()` 需用 `asyncio.run()`；测试用 `AsyncMock` 验证被调用。

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/data/test_work_signal_ingester.py::test_cli_chat_watcher_calls_ingester_after_work_log -v
```

预期：`FAILED` — `TypeError: __init__() got an unexpected keyword argument 'work_signal_ingester'`

**Step 3: 修改 CLIChatWatcher**

在 `__init__` 末尾添加字段：

```python
self._work_signal_ingester = work_signal_ingester
```

`__init__` 签名新增参数：

```python
def __init__(
    self,
    watch_paths: Optional[list[dict]] = None,
    data_dir: Optional[Path] = None,
    work_signal_ingester=None,
) -> None:
```

在 `_process_codeflicker_session` 方法末尾（`return [HuaqiDocument(...)]` 之前）追加：

```python
if self._work_signal_ingester is not None:
    import asyncio
    asyncio.run(self._work_signal_ingester.ingest())
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/data/test_work_signal_ingester.py -v
```

预期：全部 `PASSED`

**Step 5: 全量回归**

```
pytest tests/unit/layers/data/ -v
```

预期：全部 `PASSED`

**Step 6: 提交**

```
git add huaqi_src/layers/data/collectors/cli_chat_watcher.py tests/unit/layers/data/test_work_signal_ingester.py
git commit -m "feat: hook WorkSignalIngester into CLIChatWatcher"
```

---

## 阶段 3：输出层

### Task 8: CLAUDEmdWriter

读取 Telos `work_style` 等维度，重写 `~/.codeflicker/AGENTS.md` 中的 `## My Work Style` 段落。

**Files:**
- Create: `huaqi_src/layers/capabilities/codeflicker/__init__.py`
- Create: `huaqi_src/layers/capabilities/codeflicker/claude_md_writer.py`
- Create: `tests/unit/layers/capabilities/test_claude_md_writer.py`

**Step 1: 写失败测试**

```python
# tests/unit/layers/capabilities/test_claude_md_writer.py
from pathlib import Path
from unittest.mock import MagicMock
from huaqi_src.layers.capabilities.codeflicker.claude_md_writer import CLAUDEmdWriter


def _make_writer(tmp_path: Path) -> CLAUDEmdWriter:
    mock_mgr = MagicMock()
    mock_mgr.get_dimension_snippet.side_effect = lambda name: f"内容:{name}"
    agents_md = tmp_path / "AGENTS.md"
    return CLAUDEmdWriter(telos_manager=mock_mgr, agents_md_path=agents_md)


def test_sync_creates_file_if_not_exists(tmp_path):
    writer = _make_writer(tmp_path)
    writer.sync()
    agents_md = tmp_path / "AGENTS.md"
    assert agents_md.exists()
    assert "## My Work Style" in agents_md.read_text()


def test_sync_updates_existing_section(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "# 用户自定义规则\n\n旧规则内容\n\n## My Work Style\n\n旧风格\n\n## 其他段落\n\n保留内容\n"
    )
    writer = _make_writer(tmp_path)
    writer.sync()
    content = agents_md.read_text()
    assert "旧风格" not in content
    assert "内容:work_style" in content
    assert "保留内容" in content
    assert "旧规则内容" in content


def test_sync_preserves_other_content(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# 自定义\n\n我的规则\n")
    writer = _make_writer(tmp_path)
    writer.sync()
    content = agents_md.read_text()
    assert "我的规则" in content
    assert "## My Work Style" in content
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/capabilities/test_claude_md_writer.py -v
```

预期：`FAILED` — `ModuleNotFoundError`

**Step 3: 最小实现**

```python
# huaqi_src/layers/capabilities/codeflicker/__init__.py
# (空文件)
```

```python
# huaqi_src/layers/capabilities/codeflicker/claude_md_writer.py
import re
from datetime import date
from pathlib import Path
from typing import Optional

from huaqi_src.layers.growth.telos.manager import TelosManager

_DEFAULT_AGENTS_MD = Path.home() / ".codeflicker" / "AGENTS.md"
_SECTION_HEADER = "## My Work Style"
_SECTION_PATTERN = re.compile(
    r"(## My Work Style\n)(.*?)(?=\n## |\Z)", re.DOTALL
)


class CLAUDEmdWriter:

    def __init__(
        self,
        telos_manager: TelosManager,
        agents_md_path: Optional[Path] = None,
    ) -> None:
        self._mgr = telos_manager
        self._path = agents_md_path or _DEFAULT_AGENTS_MD

    def sync(self) -> None:
        section = self._build_section()
        self._upsert_section(section)

    def _build_section(self) -> str:
        parts = [f"{_SECTION_HEADER}\n"]
        parts.append(f"\n> 由 huaqi-growing 自动维护，最后更新：{date.today()}\n")
        for dim in ("work_style", "strategies", "shadows"):
            snippet = self._mgr.get_dimension_snippet(dim)
            if snippet:
                parts.append(f"\n### {dim}\n\n{snippet}\n")
        return "".join(parts)

    def _upsert_section(self, new_section: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text(new_section + "\n", encoding="utf-8")
            return
        existing = self._path.read_text(encoding="utf-8")
        match = _SECTION_PATTERN.search(existing)
        if match:
            updated = existing[: match.start()] + new_section + existing[match.end() :]
        else:
            updated = existing.rstrip("\n") + "\n\n" + new_section + "\n"
        self._path.write_text(updated, encoding="utf-8")
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/capabilities/test_claude_md_writer.py -v
```

预期：全部 `PASSED`

**Step 5: 提交**

```
git add huaqi_src/layers/capabilities/codeflicker/ tests/unit/layers/capabilities/test_claude_md_writer.py
git commit -m "feat: add CLAUDEmdWriter"
```

---

### Task 9: TelosManager 回调接入

`TelosManager.update()` 写入 `work_style` 维度后触发 `CLAUDEmdWriter.sync()`。

**Files:**
- Modify: `huaqi_src/layers/growth/telos/manager.py:113-129`
- Modify: `tests/unit/layers/growth/test_telos_manager.py`

**Step 1: 写失败测试**

在 `tests/unit/layers/growth/test_telos_manager.py` 追加：

```python
def test_update_work_style_triggers_claude_md_writer_callback(manager, telos_dir):
    from datetime import datetime, timezone
    from unittest.mock import MagicMock
    from huaqi_src.layers.growth.telos.models import HistoryEntry

    manager.init()

    mock_writer = MagicMock()
    manager.on_work_style_updated = mock_writer.sync

    manager.create_custom(
        name="work_style",
        layer=__import__(
            "huaqi_src.layers.growth.telos.models", fromlist=["DimensionLayer"]
        ).DimensionLayer.MIDDLE,
        initial_content="（待积累）",
    )
    entry = HistoryEntry(
        version=1,
        change="初始化",
        trigger="工作信号",
        confidence=0.6,
        updated_at=datetime.now(timezone.utc),
    )
    manager.update("work_style", "新工作风格内容", entry, 0.7)
    mock_writer.sync.assert_called_once()
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/growth/test_telos_manager.py::test_update_work_style_triggers_claude_md_writer_callback -v
```

预期：`FAILED` — `AssertionError: Expected 'sync' to be called once`

**Step 3: 修改 TelosManager**

在 `__init__` 末尾添加：

```python
self.on_work_style_updated: Optional[callable] = None
```

在 `update()` 方法末尾（`_git_auto_commit` 调用之后）追加：

```python
if name == "work_style" and self.on_work_style_updated is not None:
    self.on_work_style_updated()
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/growth/test_telos_manager.py -v
```

预期：全部 `PASSED`

**Step 5: 全量回归**

```
pytest tests/ -v --ignore=tests/e2e
```

预期：全部 `PASSED`

**Step 6: 提交**

```
git add huaqi_src/layers/growth/telos/manager.py tests/unit/layers/growth/test_telos_manager.py
git commit -m "feat: trigger CLAUDEmdWriter callback on work_style update"
```

---

## 阶段 4：默认注册

### Task 10: 默认注册三个数据源

在应用启动时（或 `WorkSignalIngester` 第一次使用时）自动将三个数据源加入注册表。

**Files:**
- Create: `huaqi_src/layers/data/collectors/work_sources/registry.py`
- Modify: `tests/unit/layers/data/test_work_data_source.py`

**Step 1: 写失败测试**

在 `tests/unit/layers/data/test_work_data_source.py` 追加：

```python
def test_register_defaults_adds_three_sources():
    _work_source_registry.clear()
    from huaqi_src.layers.data.collectors.work_sources.registry import register_defaults
    register_defaults()
    names = [s.name for s in get_work_sources()]
    assert "codeflicker" in names
    assert "huaqi_docs" in names
    assert "kuaishou_docs" in names
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/data/test_work_data_source.py::test_register_defaults_adds_three_sources -v
```

预期：`FAILED` — `ModuleNotFoundError`

**Step 3: 最小实现**

```python
# huaqi_src/layers/data/collectors/work_sources/registry.py
from huaqi_src.layers.data.collectors.work_data_source import register_work_source
from huaqi_src.layers.data.collectors.work_sources.codeflicker import CodeflickerSource
from huaqi_src.layers.data.collectors.work_sources.huaqi_docs import HuaqiDocsSource
from huaqi_src.layers.data.collectors.work_sources.kuaishou_docs import KuaishouDocsSource


def register_defaults() -> None:
    register_work_source(CodeflickerSource())
    register_work_source(HuaqiDocsSource())
    register_work_source(KuaishouDocsSource())
```

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/data/test_work_data_source.py -v
```

预期：全部 `PASSED`

**Step 5: 提交**

```
git add huaqi_src/layers/data/collectors/work_sources/registry.py tests/unit/layers/data/test_work_data_source.py
git commit -m "feat: add work source default registry"
```

---

## 阶段 5：new_dimension_hint 消费（可选增强）

### Task 11: DistillationPipeline 消费 new_dimension_hint

当 `step1_analyze` 返回 `new_dimension_hint` 时，若维度不存在则自动创建后追加到待处理列表。

**Files:**
- Modify: `huaqi_src/layers/data/raw_signal/pipeline.py:38-42`（Step1 调用之后）
- Modify: `tests/unit/layers/data/test_raw_signal_pipeline.py`

**Step 1: 写失败测试**

在 `tests/unit/layers/data/test_raw_signal_pipeline.py` 追加：

```python
async def test_pipeline_creates_dimension_from_new_dimension_hint(tmp_path):
    import json
    pipeline, store = make_pipeline(tmp_path)
    now = datetime.now(timezone.utc)

    signal = RawSignal(
        user_id="u1",
        source_type=SourceType.WORK_DOC,
        timestamp=now,
        content="我有很强的项目管理能力",
    )
    store.save(signal)

    step1_response = json.dumps({
        "dimensions": ["goals"],
        "emotion": "positive",
        "intensity": 0.7,
        "signal_strength": "strong",
        "strong_reason": "工作技能",
        "summary": "项目管理能力",
        "new_dimension_hint": "project_management",
        "has_people": False,
        "mentioned_names": [],
    })
    combined_response = json.dumps({
        "should_update": False,
        "new_content": None,
        "consistency_score": 0.3,
        "history_entry": None,
        "is_growth_event": False,
        "growth_title": None,
        "growth_narrative": None,
    })

    mock_llm = pipeline._engine._llm
    mock_llm.invoke.return_value = MagicMock(content=step1_response)
    from unittest.mock import AsyncMock
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=combined_response))

    await pipeline.process(signal)

    from huaqi_src.config.errors import DimensionNotFoundError
    try:
        pipeline._mgr.get("project_management")
        dimension_created = True
    except DimensionNotFoundError:
        dimension_created = False
    assert dimension_created
```

**Step 2: 确认测试失败**

```
pytest tests/unit/layers/data/test_raw_signal_pipeline.py::test_pipeline_creates_dimension_from_new_dimension_hint -v
```

预期：`FAILED` — `assert False`（维度未被创建）

**Step 3: 修改 pipeline.py**

在 `process()` 中，`self._signal_store.mark_processed(signal.id)` 之后紧接着追加：

```python
if step1_result.new_dimension_hint:
    hint = step1_result.new_dimension_hint
    try:
        self._mgr.get(hint)
    except Exception:
        self._mgr.create_custom(
            name=hint,
            layer=DimensionLayer.SURFACE,
            initial_content="（待积累）",
        )
    if hint not in step1_result.dimensions:
        step1_result.dimensions.append(hint)
```

同时在文件顶部 import 补充：

```python
from huaqi_src.layers.growth.telos.models import DimensionLayer, STANDARD_DIMENSION_LAYERS
```

（若 `STANDARD_DIMENSION_LAYERS` 已导入则去掉重复部分）

**Step 4: 确认测试通过**

```
pytest tests/unit/layers/data/test_raw_signal_pipeline.py -v
```

预期：全部 `PASSED`

**Step 5: 全量回归**

```
pytest tests/ -v --ignore=tests/e2e
```

预期：全部 `PASSED`

**Step 6: 提交**

```
git add huaqi_src/layers/data/raw_signal/pipeline.py tests/unit/layers/data/test_raw_signal_pipeline.py
git commit -m "feat: pipeline consumes new_dimension_hint to auto-create dimensions"
```

---

## 总体验证

完成所有 Task 后，执行完整测试确认无回归：

```
pytest tests/ -v --ignore=tests/e2e
```

预期：全部 `PASSED`

---

## 文件清单汇总

| 文件 | 动作 |
|------|------|
| `huaqi_src/layers/data/raw_signal/models.py` | 微调：`SourceType.WORK_DOC` |
| `huaqi_src/layers/data/collectors/work_data_source.py` | 新增：抽象基类 + 注册表 |
| `huaqi_src/layers/data/collectors/work_sources/__init__.py` | 新增：空文件 |
| `huaqi_src/layers/data/collectors/work_sources/codeflicker.py` | 新增 |
| `huaqi_src/layers/data/collectors/work_sources/huaqi_docs.py` | 新增 |
| `huaqi_src/layers/data/collectors/work_sources/kuaishou_docs.py` | 新增（占位） |
| `huaqi_src/layers/data/collectors/work_sources/registry.py` | 新增：默认注册 |
| `huaqi_src/layers/data/collectors/work_signal_ingester.py` | 新增 |
| `huaqi_src/layers/data/collectors/cli_chat_watcher.py` | 微调：新增 `work_signal_ingester` 参数 |
| `huaqi_src/layers/capabilities/codeflicker/__init__.py` | 新增：空文件 |
| `huaqi_src/layers/capabilities/codeflicker/claude_md_writer.py` | 新增 |
| `huaqi_src/layers/growth/telos/manager.py` | 微调：`on_work_style_updated` 回调 |
| `huaqi_src/layers/data/raw_signal/pipeline.py` | 微调（阶段 5）：消费 `new_dimension_hint` |
