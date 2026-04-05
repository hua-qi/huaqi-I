# World Pipeline 与定时任务补跑机制 Implementation Plan

**Goal:** 打通 Pipeline 采集到晨报国际新闻的数据链路，并建立定时任务执行日志与补跑机制。

**Architecture:** 新增独立的 `WorldPipeline` 采集流程写入 `world/YYYY-MM-DD.md`；在 SQLite 的 `scheduler.db` 新增 `job_execution_log` 表记录任务历史；CLI 启动时通过 `StartupJobRecovery` 扫描并后台补跑遗漏任务。

**Tech Stack:** Python, APScheduler (CronTrigger), SQLite (sqlite3 标准库), Pydantic, Typer, feedparser (已有), Rich

---

## 背景知识

在开始之前，先了解几个关键点：

### 项目结构
```
huaqi_src/
├── layers/data/world/         # 世界新闻采集（已有 fetcher.py + storage.py）
├── scheduler/                 # APScheduler 定时任务（jobs.py 注册5个任务）
├── config/manager.py          # AppConfig (Pydantic BaseModel)
└── cli/
    ├── context.py             # ensure_initialized() 在此
    └── commands/              # Typer 子命令
```

### 已有组件（不用重写，直接用）
- `WorldNewsFetcher(sources)` → `fetch_all()` → `list[HuaqiDocument]`
- `WorldNewsStorage(data_dir)` → `save(docs, date)` 写入 `{data_dir}/world/YYYY-MM-DD.md`
- `RSSSource(url, name)` → 从 RSS Feed 抓取新闻
- `get_scheduler_db_path()` → 返回 `{data_dir}/scheduler.db` 的 Path

### 测试运行命令
```bash
pytest tests/ -v                                           # 全部测试
pytest tests/unit/scheduler/ -v                           # 调度器相关
pytest tests/unit/layers/data/world/ -v                   # world 模块
pytest tests/unit/scheduler/test_world_pipeline.py -v     # 单个文件
```

---

## Task 1: WorldPipeline — 独立采集流程

**Files:**
- Create: `huaqi_src/layers/data/world/pipeline.py`
- Create: `tests/unit/layers/data/world/test_pipeline.py`

### Step 1: 写失败测试

```python
# tests/unit/layers/data/world/test_pipeline.py
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from huaqi_src.layers.data.world.pipeline import WorldPipeline


def test_world_pipeline_run_saves_docs(tmp_path):
    mock_doc = MagicMock()
    mock_doc.doc_type = "world_news"

    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage") as MockStorage:
        MockFetcher.return_value.fetch_all.return_value = [mock_doc]

        pipeline = WorldPipeline(data_dir=tmp_path)
        pipeline.run()

        MockFetcher.return_value.fetch_all.assert_called_once()
        MockStorage.return_value.save.assert_called_once()


def test_world_pipeline_run_with_custom_date(tmp_path):
    target_date = datetime.date(2026, 1, 1)
    mock_doc = MagicMock()

    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage") as MockStorage:
        MockFetcher.return_value.fetch_all.return_value = [mock_doc]

        pipeline = WorldPipeline(data_dir=tmp_path)
        pipeline.run(date=target_date)

        _, call_kwargs = MockStorage.return_value.save.call_args
        assert call_kwargs.get("date") == target_date or \
               MockStorage.return_value.save.call_args[0][1] == target_date


def test_world_pipeline_run_returns_false_when_no_docs(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage"):
        MockFetcher.return_value.fetch_all.return_value = []

        pipeline = WorldPipeline(data_dir=tmp_path)
        result = pipeline.run()

        assert result is False


def test_world_pipeline_run_returns_true_on_success(tmp_path):
    mock_doc = MagicMock()

    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage"):
        MockFetcher.return_value.fetch_all.return_value = [mock_doc]

        pipeline = WorldPipeline(data_dir=tmp_path)
        result = pipeline.run()

        assert result is True


def test_world_pipeline_run_returns_false_on_exception(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage"):
        MockFetcher.return_value.fetch_all.side_effect = RuntimeError("网络错误")

        pipeline = WorldPipeline(data_dir=tmp_path)
        result = pipeline.run()

        assert result is False
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/layers/data/world/test_pipeline.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.layers.data.world.pipeline'`

### Step 3: 实现 WorldPipeline

```python
# huaqi_src/layers/data/world/pipeline.py
import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.layers.data.world.fetcher import WorldNewsFetcher
from huaqi_src.layers.data.world.storage import WorldNewsStorage
from huaqi_src.layers.data.world.sources.rss_source import RSSSource

DEFAULT_RSS_FEEDS = [
    ("https://feeds.bbci.co.uk/news/technology/rss.xml", "BBC科技"),
    ("https://rss.cnn.com/rss/money_news_international.rss", "CNN财经"),
    ("https://feeds.reuters.com/reuters/worldNews", "路透社国际"),
]


class WorldPipeline:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def run(self, date: Optional[datetime.date] = None) -> bool:
        try:
            sources = [RSSSource(url, name) for url, name in DEFAULT_RSS_FEEDS]
            fetcher = WorldNewsFetcher(sources=sources)
            docs = fetcher.fetch_all()
            if not docs:
                print("[WorldPipeline] 未获取到任何文档")
                return False
            storage = WorldNewsStorage(data_dir=self._data_dir)
            storage.save(docs, date=date)
            print(f"[WorldPipeline] 已保存 {len(docs)} 篇文档")
            return True
        except Exception as e:
            print(f"[WorldPipeline] 执行失败: {e}")
            return False
```

### Step 4: 运行测试确认通过

```bash
pytest tests/unit/layers/data/world/test_pipeline.py -v
```

预期：5 passed

### Step 5: 提交

```bash
git add huaqi_src/layers/data/world/pipeline.py tests/unit/layers/data/world/test_pipeline.py
git commit -m "feat: add WorldPipeline for independent news collection"
```

---

## Task 2: JobExecutionLog — SQLite 执行日志

**Files:**
- Create: `huaqi_src/scheduler/execution_log.py`
- Create: `tests/unit/scheduler/test_execution_log.py`

### Step 1: 写失败测试

```python
# tests/unit/scheduler/test_execution_log.py
import datetime
from pathlib import Path
from huaqi_src.scheduler.execution_log import JobExecutionLog


def test_write_start_creates_entry(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))

    assert isinstance(entry_id, int)
    assert entry_id > 0


def test_write_result_updates_entry(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))
    log.write_result(entry_id, "success")

    assert log.has_success("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))


def test_has_success_returns_false_when_only_running(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    log.write_start("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))

    assert not log.has_success("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))


def test_has_success_returns_false_when_failed(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))
    log.write_result(entry_id, "failed", error="超时")

    assert not log.has_success("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))


def test_get_latest_returns_entries_in_range(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    since = datetime.datetime(2026, 5, 1, 0, 0)
    until = datetime.datetime(2026, 5, 4, 23, 59)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 3, 8, 0))
    log.write_result(entry_id, "success")

    results = log.get_latest("morning_brief", since, until)
    assert len(results) == 1
    assert results[0].job_id == "morning_brief"
    assert results[0].status == "success"


def test_get_latest_excludes_out_of_range(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    since = datetime.datetime(2026, 5, 4, 0, 0)
    until = datetime.datetime(2026, 5, 4, 23, 59)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 1, 8, 0))
    log.write_result(entry_id, "success")

    results = log.get_latest("morning_brief", since, until)
    assert len(results) == 0
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/scheduler/test_execution_log.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.scheduler.execution_log'`

### Step 3: 实现 JobExecutionLog

```python
# huaqi_src/scheduler/execution_log.py
import sqlite3
import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class LogEntry:
    id: int
    job_id: str
    scheduled_at: datetime.datetime
    status: str
    started_at: datetime.datetime
    finished_at: Optional[datetime.datetime]
    error: Optional[str]


class JobExecutionLog:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_execution_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id       TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'running',
                    started_at   TEXT NOT NULL,
                    finished_at  TEXT,
                    error        TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_scheduled
                ON job_execution_log (job_id, scheduled_at)
            """)

    def write_start(self, job_id: str, scheduled_at: datetime.datetime) -> int:
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO job_execution_log (job_id, scheduled_at, status, started_at) VALUES (?, ?, 'running', ?)",
                (job_id, scheduled_at.isoformat(), now),
            )
            return cursor.lastrowid

    def write_result(self, entry_id: int, status: str, error: Optional[str] = None):
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE job_execution_log SET status=?, finished_at=?, error=? WHERE id=?",
                (status, now, error, entry_id),
            )

    def has_success(self, job_id: str, scheduled_at: datetime.datetime) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM job_execution_log WHERE job_id=? AND scheduled_at=? AND status='success' LIMIT 1",
                (job_id, scheduled_at.isoformat()),
            ).fetchone()
            return row is not None

    def get_latest(
        self, job_id: str, since: datetime.datetime, until: datetime.datetime
    ) -> List[LogEntry]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, job_id, scheduled_at, status, started_at, finished_at, error
                   FROM job_execution_log
                   WHERE job_id=? AND scheduled_at>=? AND scheduled_at<=?
                   ORDER BY scheduled_at DESC""",
                (job_id, since.isoformat(), until.isoformat()),
            ).fetchall()
        return [
            LogEntry(
                id=r[0],
                job_id=r[1],
                scheduled_at=datetime.datetime.fromisoformat(r[2]),
                status=r[3],
                started_at=datetime.datetime.fromisoformat(r[4]),
                finished_at=datetime.datetime.fromisoformat(r[5]) if r[5] else None,
                error=r[6],
            )
            for r in rows
        ]
```

### Step 4: 运行测试确认通过

```bash
pytest tests/unit/scheduler/test_execution_log.py -v
```

预期：6 passed

### Step 5: 提交

```bash
git add huaqi_src/scheduler/execution_log.py tests/unit/scheduler/test_execution_log.py
git commit -m "feat: add JobExecutionLog for scheduler history tracking"
```

---

## Task 3: MissedJobScanner — 遗漏任务扫描器

**Files:**
- Create: `huaqi_src/scheduler/missed_job_scanner.py`
- Create: `tests/unit/scheduler/test_missed_job_scanner.py`

### 背景
`CronTrigger.from_crontab(cron).get_next_fire_time(None, since)` 可以迭代计算 cron 在某时间之后的下次触发时间。通过循环调用，可以枚举一个时间窗口内所有应触发时间点，再逐一比对执行日志。

### Step 1: 写失败测试

```python
# tests/unit/scheduler/test_missed_job_scanner.py
import datetime
from unittest.mock import MagicMock, patch
from huaqi_src.scheduler.missed_job_scanner import MissedJobScanner, MissedJob

JOB_CONFIGS = {
    "morning_brief": {
        "cron": "0 8 * * *",
        "display_name": "晨间简报",
    }
}


def test_scanner_returns_missed_job_when_no_log(tmp_path):
    db_path = tmp_path / "scheduler.db"

    since = datetime.datetime(2026, 5, 3, 0, 0)
    until = datetime.datetime(2026, 5, 4, 9, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since, until)

    assert len(missed) >= 1
    assert any(m.job_id == "morning_brief" for m in missed)
    assert all(isinstance(m, MissedJob) for m in missed)


def test_scanner_skips_job_with_success_log(tmp_path):
    from huaqi_src.scheduler.execution_log import JobExecutionLog

    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    scheduled_at = datetime.datetime(2026, 5, 4, 8, 0)
    entry_id = log.write_start("morning_brief", scheduled_at)
    log.write_result(entry_id, "success")

    since = datetime.datetime(2026, 5, 4, 0, 0)
    until = datetime.datetime(2026, 5, 4, 9, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since, until)

    assert not any(
        m.job_id == "morning_brief" and m.scheduled_at == scheduled_at
        for m in missed
    )


def test_scanner_includes_failed_job_as_missed(tmp_path):
    from huaqi_src.scheduler.execution_log import JobExecutionLog

    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    scheduled_at = datetime.datetime(2026, 5, 4, 8, 0)
    entry_id = log.write_start("morning_brief", scheduled_at)
    log.write_result(entry_id, "failed", error="超时")

    since = datetime.datetime(2026, 5, 4, 0, 0)
    until = datetime.datetime(2026, 5, 4, 9, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since, until)

    assert any(
        m.job_id == "morning_brief" and m.scheduled_at == scheduled_at
        for m in missed
    )


def test_scanner_returns_empty_when_since_equals_until(tmp_path):
    db_path = tmp_path / "scheduler.db"
    now = datetime.datetime(2026, 5, 4, 12, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since=now, until=now)

    assert missed == []


def test_missed_job_has_correct_fields(tmp_path):
    db_path = tmp_path / "scheduler.db"
    since = datetime.datetime(2026, 5, 4, 0, 0)
    until = datetime.datetime(2026, 5, 4, 9, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since, until)

    for m in missed:
        assert hasattr(m, "job_id")
        assert hasattr(m, "scheduled_at")
        assert hasattr(m, "display_name")
        assert isinstance(m.scheduled_at, datetime.datetime)
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/scheduler/test_missed_job_scanner.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.scheduler.missed_job_scanner'`

### Step 3: 实现 MissedJobScanner

```python
# huaqi_src/scheduler/missed_job_scanner.py
import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from apscheduler.triggers.cron import CronTrigger

from huaqi_src.scheduler.execution_log import JobExecutionLog


@dataclass
class MissedJob:
    job_id: str
    scheduled_at: datetime.datetime
    display_name: str


class MissedJobScanner:
    def __init__(
        self,
        db_path: Path,
        job_configs: Dict[str, dict],
        timezone: str = "Asia/Shanghai",
    ):
        self.log = JobExecutionLog(db_path)
        self.job_configs = job_configs
        self.timezone = timezone

    def scan(self, since: datetime.datetime, until: datetime.datetime) -> List[MissedJob]:
        if since >= until:
            return []

        missed: List[MissedJob] = []
        for job_id, config in self.job_configs.items():
            cron = config.get("cron", "")
            display_name = config.get("display_name", job_id)
            if not cron:
                continue
            fire_times = self._get_fire_times(cron, since, until)
            for fire_time in fire_times:
                if not self.log.has_success(job_id, fire_time):
                    missed.append(MissedJob(
                        job_id=job_id,
                        scheduled_at=fire_time,
                        display_name=display_name,
                    ))
        return missed

    def _get_fire_times(
        self,
        cron: str,
        since: datetime.datetime,
        until: datetime.datetime,
    ) -> List[datetime.datetime]:
        trigger = CronTrigger.from_crontab(cron, timezone=self.timezone)
        fire_times = []
        current = since
        while True:
            next_time = trigger.get_next_fire_time(None, current)
            if next_time is None:
                break
            next_naive = next_time.replace(tzinfo=None) if next_time.tzinfo else next_time
            if next_naive > until:
                break
            fire_times.append(next_naive)
            current = next_time
        return fire_times
```

### Step 4: 运行测试确认通过

```bash
pytest tests/unit/scheduler/test_missed_job_scanner.py -v
```

预期：5 passed

### Step 5: 提交

```bash
git add huaqi_src/scheduler/missed_job_scanner.py tests/unit/scheduler/test_missed_job_scanner.py
git commit -m "feat: add MissedJobScanner for detecting missed scheduled jobs"
```

---

## Task 4: SchedulerJobConfig — 配置开关

**Files:**
- Modify: `huaqi_src/config/manager.py`
- Create: `tests/unit/config/test_scheduler_job_config.py`

### Step 1: 写失败测试

```python
# tests/unit/config/test_scheduler_job_config.py
from huaqi_src.config.manager import AppConfig, SchedulerJobConfig


def test_scheduler_job_config_defaults():
    cfg = SchedulerJobConfig()
    assert cfg.enabled is True
    assert cfg.cron is None


def test_scheduler_job_config_custom():
    cfg = SchedulerJobConfig(enabled=False, cron="0 9 * * *")
    assert cfg.enabled is False
    assert cfg.cron == "0 9 * * *"


def test_app_config_has_scheduler_jobs_field():
    config = AppConfig()
    assert hasattr(config, "scheduler_jobs")
    assert isinstance(config.scheduler_jobs, dict)
    assert config.scheduler_jobs == {}


def test_app_config_scheduler_jobs_can_be_set():
    config = AppConfig(
        scheduler_jobs={
            "morning_brief": SchedulerJobConfig(enabled=True, cron="0 7 * * *"),
            "weekly_report": SchedulerJobConfig(enabled=False),
        }
    )
    assert config.scheduler_jobs["morning_brief"].cron == "0 7 * * *"
    assert config.scheduler_jobs["weekly_report"].enabled is False


def test_app_config_serializes_scheduler_jobs():
    config = AppConfig(
        scheduler_jobs={
            "morning_brief": SchedulerJobConfig(enabled=True, cron="0 8 * * *"),
        }
    )
    data = config.model_dump()
    assert "scheduler_jobs" in data
    assert data["scheduler_jobs"]["morning_brief"]["enabled"] is True
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/config/test_scheduler_job_config.py -v
```

预期：`ImportError: cannot import name 'SchedulerJobConfig' from 'huaqi_src.config.manager'`

### Step 3: 修改 AppConfig

在 `huaqi_src/config/manager.py` 的 `MemoryConfig` 类定义之后，`AppConfig` 之前，新增 `SchedulerJobConfig`：

```python
# 在 MemoryConfig 类之后添加
class SchedulerJobConfig(BaseModel):
    enabled: bool = True
    cron: Optional[str] = None
```

然后在 `AppConfig` 的 `modules` 字段之后添加：

```python
    scheduler_jobs: Dict[str, "SchedulerJobConfig"] = Field(default_factory=dict)
```

完整修改后的 `AppConfig`：
```python
class AppConfig(BaseModel):
    version: str = "0.1.0"
    data_dir: Optional[str] = None
    llm_default_provider: str = "dummy"
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    interface_theme: str = "default"
    interface_language: str = "zh"
    custom: Dict[str, Any] = Field(default_factory=dict)
    modules: Dict[str, bool] = Field(default_factory=dict)
    scheduler_jobs: Dict[str, SchedulerJobConfig] = Field(default_factory=dict)
```

### Step 4: 运行测试确认通过

```bash
pytest tests/unit/config/test_scheduler_job_config.py -v
```

预期：5 passed

### Step 5: 提交

```bash
git add huaqi_src/config/manager.py tests/unit/config/test_scheduler_job_config.py
git commit -m "feat: add SchedulerJobConfig to AppConfig"
```

---

## Task 5: jobs.py 接入配置开关与执行日志

**Files:**
- Modify: `huaqi_src/scheduler/jobs.py`
- Modify: `tests/unit/scheduler/test_jobs.py`

### Step 1: 写失败测试（追加到现有文件）

在 `tests/unit/scheduler/test_jobs.py` 末尾追加：

```python
def test_register_jobs_skips_disabled_job():
    from unittest.mock import MagicMock
    from huaqi_src.config.manager import AppConfig, SchedulerJobConfig
    from huaqi_src.scheduler.jobs import register_default_jobs

    mock_manager = MagicMock()
    config = AppConfig(
        scheduler_jobs={"morning_brief": SchedulerJobConfig(enabled=False)}
    )

    register_default_jobs(mock_manager, config=config)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "morning_brief" not in call_ids


def test_register_jobs_uses_custom_cron():
    from unittest.mock import MagicMock, call
    from huaqi_src.config.manager import AppConfig, SchedulerJobConfig
    from huaqi_src.scheduler.jobs import register_default_jobs

    mock_manager = MagicMock()
    config = AppConfig(
        scheduler_jobs={"morning_brief": SchedulerJobConfig(enabled=True, cron="0 7 * * *")}
    )

    register_default_jobs(mock_manager, config=config)

    cron_calls = {call.args[0]: call.args[2] for call in mock_manager.add_cron_job.call_args_list}
    assert cron_calls.get("morning_brief") == "0 7 * * *"


def test_register_jobs_uses_default_cron_when_not_configured():
    from unittest.mock import MagicMock
    from huaqi_src.config.manager import AppConfig
    from huaqi_src.scheduler.jobs import register_default_jobs

    mock_manager = MagicMock()
    config = AppConfig()

    register_default_jobs(mock_manager, config=config)

    cron_calls = {call.args[0]: call.args[2] for call in mock_manager.add_cron_job.call_args_list}
    assert cron_calls.get("morning_brief") == "0 8 * * *"


def test_register_jobs_includes_world_fetch():
    from unittest.mock import MagicMock
    from huaqi_src.scheduler.jobs import register_default_jobs

    mock_manager = MagicMock()
    register_default_jobs(mock_manager)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "world_fetch" in call_ids
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/scheduler/test_jobs.py -v
```

预期：新增的4个测试 FAIL（`register_default_jobs` 不接受 `config` 参数 / 缺少 `world_fetch`）

### Step 3: 修改 jobs.py

在 `jobs.py` 中做以下修改：

1. 新增 `_run_world_fetch` 函数：
```python
def _run_world_fetch():
    from huaqi_src.layers.data.world.pipeline import WorldPipeline
    try:
        pipeline = WorldPipeline()
        pipeline.run()
    except Exception as e:
        print(f"[WorldFetch] 采集失败: {e}")
```

2. 更新 `KNOWN_JOB_IDS` 加入 `world_fetch`：
```python
KNOWN_JOB_IDS = {
    "morning_brief",
    "daily_report",
    "weekly_report",
    "quarterly_report",
    "learning_daily_push",
    "world_fetch",
}
```

3. 定义各任务的默认 cron 和 display_name：
```python
_DEFAULT_JOB_CONFIGS = {
    "morning_brief":      {"cron": "0 8 * * *",        "display_name": "晨间简报",   "func": "_run_morning_brief"},
    "daily_report":       {"cron": "0 23 * * *",       "display_name": "日终复盘",   "func": "_run_daily_report"},
    "weekly_report":      {"cron": "0 21 * * 0",       "display_name": "周报",       "func": "_run_weekly_report"},
    "quarterly_report":   {"cron": "0 22 28-31 3,6,9,12 *", "display_name": "季报", "func": "_run_quarterly_report"},
    "learning_daily_push":{"cron": "0 21 * * *",       "display_name": "学习推送",   "func": "_run_learning_push"},
    "world_fetch":        {"cron": "0 7 * * *",        "display_name": "世界新闻采集","func": "_run_world_fetch"},
}

_JOB_FUNCS = {
    "morning_brief": _run_morning_brief,
    "daily_report": _run_daily_report,
    "weekly_report": _run_weekly_report,
    "quarterly_report": _run_quarterly_report,
    "learning_daily_push": _run_learning_push,
    "world_fetch": _run_world_fetch,
}
```

4. 修改 `register_default_jobs` 签名与逻辑：
```python
def register_default_jobs(manager: SchedulerManager, config: "Optional[AppConfig]" = None):
    from typing import Optional
    _cleanup_unknown_jobs(manager)
    for job_id, defaults in _DEFAULT_JOB_CONFIGS.items():
        job_config = None
        if config is not None:
            job_config = config.scheduler_jobs.get(job_id)
        if job_config is not None and not job_config.enabled:
            continue
        cron = (job_config.cron if job_config and job_config.cron else defaults["cron"])
        func = _JOB_FUNCS[job_id]
        manager.add_cron_job(job_id, func=func, cron=cron)
```

### Step 4: 运行测试确认通过

```bash
pytest tests/unit/scheduler/test_jobs.py -v
```

预期：全部通过（包括原有的2个 + 新增的4个）

### Step 5: 提交

```bash
git add huaqi_src/scheduler/jobs.py tests/unit/scheduler/test_jobs.py
git commit -m "feat: jobs.py supports config switch and custom cron, add world_fetch job"
```

---

## Task 6: StartupJobRecovery — 启动补跑编排

**Files:**
- Create: `huaqi_src/scheduler/startup_recovery.py`
- Create: `tests/unit/scheduler/test_startup_recovery.py`

### 背景
`cli_last_opened` 时间戳存储在 `{data_dir}/scheduler_meta.json` 文件中，格式为 `{"cli_last_opened": "2026-05-03T10:00:00"}`。

### Step 1: 写失败测试

```python
# tests/unit/scheduler/test_startup_recovery.py
import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from huaqi_src.scheduler.startup_recovery import StartupJobRecovery, load_last_opened, save_last_opened


def test_load_last_opened_returns_none_when_file_missing(tmp_path):
    result = load_last_opened(tmp_path)
    assert result is None


def test_save_and_load_last_opened(tmp_path):
    dt = datetime.datetime(2026, 5, 3, 10, 0, 0)
    save_last_opened(tmp_path, dt)
    result = load_last_opened(tmp_path)
    assert result == dt


def test_recovery_updates_last_opened(tmp_path):
    db_path = tmp_path / "scheduler.db"
    job_configs = {}

    before = datetime.datetime(2026, 5, 3, 10, 0)
    save_last_opened(tmp_path, before)

    recovery = StartupJobRecovery(data_dir=tmp_path, db_path=db_path, job_configs=job_configs)
    recovery.run(notify_callback=None)

    after = load_last_opened(tmp_path)
    assert after > before


def test_recovery_calls_notify_when_missed_jobs(tmp_path):
    db_path = tmp_path / "scheduler.db"
    job_configs = {
        "morning_brief": {"cron": "0 8 * * *", "display_name": "晨间简报"}
    }

    since = datetime.datetime.now() - datetime.timedelta(days=2)
    save_last_opened(tmp_path, since)

    notify_mock = MagicMock()
    recovery = StartupJobRecovery(data_dir=tmp_path, db_path=db_path, job_configs=job_configs)
    recovery.run(notify_callback=notify_mock)

    notify_mock.assert_called_once()
    call_args = notify_mock.call_args[0]
    assert len(call_args) >= 1


def test_recovery_does_not_call_notify_when_no_missed_jobs(tmp_path):
    from huaqi_src.scheduler.execution_log import JobExecutionLog

    db_path = tmp_path / "scheduler.db"
    job_configs = {
        "morning_brief": {"cron": "0 8 * * *", "display_name": "晨间简报"}
    }
    log = JobExecutionLog(db_path)

    now = datetime.datetime.now()
    since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    scheduled_at = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if scheduled_at > now:
        save_last_opened(tmp_path, now + datetime.timedelta(minutes=1))
    else:
        entry_id = log.write_start("morning_brief", scheduled_at)
        log.write_result(entry_id, "success")
        save_last_opened(tmp_path, since)

    notify_mock = MagicMock()
    recovery = StartupJobRecovery(data_dir=tmp_path, db_path=db_path, job_configs=job_configs)

    if scheduled_at > now:
        recovery.run(notify_callback=notify_mock)
        notify_mock.assert_not_called()
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/scheduler/test_startup_recovery.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.scheduler.startup_recovery'`

### Step 3: 实现 StartupJobRecovery

```python
# huaqi_src/scheduler/startup_recovery.py
import datetime
import json
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

from huaqi_src.scheduler.missed_job_scanner import MissedJob, MissedJobScanner


_META_FILE = "scheduler_meta.json"


def load_last_opened(data_dir: Path) -> Optional[datetime.datetime]:
    meta_path = Path(data_dir) / _META_FILE
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        raw = data.get("cli_last_opened")
        if raw:
            return datetime.datetime.fromisoformat(raw)
    except Exception:
        pass
    return None


def save_last_opened(data_dir: Path, dt: datetime.datetime):
    meta_path = Path(data_dir) / _META_FILE
    existing: dict = {}
    if meta_path.exists():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["cli_last_opened"] = dt.isoformat()
    meta_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


class StartupJobRecovery:
    def __init__(
        self,
        data_dir: Path,
        db_path: Path,
        job_configs: Dict[str, dict],
        timezone: str = "Asia/Shanghai",
    ):
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.job_configs = job_configs
        self.timezone = timezone

    def run(self, notify_callback: Optional[Callable[[List[MissedJob]], None]]):
        now = datetime.datetime.now()
        last_opened = load_last_opened(self.data_dir)
        save_last_opened(self.data_dir, now)

        if last_opened is None:
            return

        scanner = MissedJobScanner(
            db_path=self.db_path,
            job_configs=self.job_configs,
            timezone=self.timezone,
        )
        missed = scanner.scan(last_opened, now)

        if not missed:
            return

        if notify_callback is not None:
            notify_callback(missed)

        t = threading.Thread(
            target=self._run_missed_jobs,
            args=(missed,),
            daemon=True,
        )
        t.start()

    def _run_missed_jobs(self, missed: List[MissedJob]):
        from huaqi_src.scheduler.execution_log import JobExecutionLog
        log = JobExecutionLog(self.db_path)

        _job_funcs = self._get_job_funcs()
        for missed_job in missed:
            func = _job_funcs.get(missed_job.job_id)
            if func is None:
                continue
            entry_id = log.write_start(missed_job.job_id, missed_job.scheduled_at)
            try:
                func()
                log.write_result(entry_id, "success")
            except Exception as e:
                log.write_result(entry_id, "failed", error=str(e))

    def _get_job_funcs(self) -> dict:
        from huaqi_src.scheduler.jobs import _JOB_FUNCS
        return _JOB_FUNCS
```

### Step 4: 运行测试确认通过

```bash
pytest tests/unit/scheduler/test_startup_recovery.py -v
```

预期：5 passed

### Step 5: 提交

```bash
git add huaqi_src/scheduler/startup_recovery.py tests/unit/scheduler/test_startup_recovery.py
git commit -m "feat: add StartupJobRecovery for missed job catchup on CLI startup"
```

---

## Task 7: WorldProvider lazy 补采

**Files:**
- Modify: `huaqi_src/layers/capabilities/reports/providers/world.py`
- Modify: `tests/unit/layers/data/world/` (新增 `test_world_provider.py`)

### Step 1: 写失败测试

```python
# tests/unit/layers/data/world/test_world_provider.py
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
from huaqi_src.layers.capabilities.reports.providers import DateRange


def _make_date_range(date_str: str):
    d = datetime.date.fromisoformat(date_str)
    return DateRange(start=d, end=d)


def test_world_provider_returns_content_when_file_exists(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "2026-05-04.md").write_text("# 世界新闻\n测试内容", encoding="utf-8")

    provider = WorldProvider(data_dir=tmp_path)
    result = provider.get_context("morning", _make_date_range("2026-05-04"))

    assert result is not None
    assert "世界热点" in result or "世界新闻" in result or "测试内容" in result


def test_world_provider_triggers_lazy_fetch_when_file_missing(tmp_path):
    with patch("huaqi_src.layers.capabilities.reports.providers.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = True
        (tmp_path / "world").mkdir()
        (tmp_path / "world" / "2026-05-04.md").write_text("lazy 采集内容", encoding="utf-8")

        provider = WorldProvider(data_dir=tmp_path)

        world_file = tmp_path / "world" / "2026-05-04.md"
        world_file.unlink()

        def fake_run(**kwargs):
            world_file.write_text("lazy 采集内容", encoding="utf-8")
            return True

        MockPipeline.return_value.run.side_effect = fake_run
        result = provider.get_context("morning", _make_date_range("2026-05-04"))

        MockPipeline.return_value.run.assert_called_once()
        assert result is not None


def test_world_provider_returns_none_when_lazy_fetch_fails(tmp_path):
    with patch("huaqi_src.layers.capabilities.reports.providers.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = False

        provider = WorldProvider(data_dir=tmp_path)
        result = provider.get_context("morning", _make_date_range("2026-05-04"))

        assert result is None


def test_world_provider_returns_none_when_lazy_fetch_raises(tmp_path):
    with patch("huaqi_src.layers.capabilities.reports.providers.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.side_effect = RuntimeError("网络错误")

        provider = WorldProvider(data_dir=tmp_path)
        result = provider.get_context("morning", _make_date_range("2026-05-04"))

        assert result is None
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/layers/data/world/test_world_provider.py -v
```

预期：lazy 补采相关的3个测试 FAIL（`WorldProvider.get_context` 中没有调用 `WorldPipeline`）

### Step 3: 修改 WorldProvider

```python
# huaqi_src/layers/capabilities/reports/providers/world.py
from pathlib import Path
from typing import Optional

from huaqi_src.layers.capabilities.reports.providers import DataProvider, DateRange, register


class WorldProvider(DataProvider):
    name = "world"
    priority = 10
    supported_reports = ["morning", "daily"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        today = date_range.end.isoformat()
        world_file = self._data_dir / "world" / f"{today}.md"
        if not world_file.exists():
            world_file = self._lazy_fetch(today)
        if world_file is None or not world_file.exists():
            return None
        content = world_file.read_text(encoding="utf-8")[:1000]
        return f"## 今日世界热点\n{content}"

    def _lazy_fetch(self, date_str: str) -> "Optional[Path]":
        try:
            from huaqi_src.layers.data.world.pipeline import WorldPipeline
            import datetime
            pipeline = WorldPipeline(data_dir=self._data_dir)
            target_date = datetime.date.fromisoformat(date_str)
            success = pipeline.run(date=target_date)
            if not success:
                return None
            return self._data_dir / "world" / f"{date_str}.md"
        except Exception as e:
            print(f"[WorldProvider] lazy 补采失败: {e}")
            return None


try:
    from huaqi_src.config.paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(WorldProvider(_data_dir))
except Exception:
    pass
```

### Step 4: 运行测试确认通过

```bash
pytest tests/unit/layers/data/world/test_world_provider.py -v
```

预期：4 passed

### Step 5: 提交

```bash
git add huaqi_src/layers/capabilities/reports/providers/world.py tests/unit/layers/data/world/test_world_provider.py
git commit -m "feat: WorldProvider adds lazy fetch fallback via WorldPipeline"
```

---

## Task 8: CLI world 命令

**Files:**
- Create: `huaqi_src/cli/commands/world.py`
- Modify: `huaqi_src/cli/main.py` 或入口文件（注册子命令）
- Create: `tests/unit/cli/commands/test_world_command.py`

### Step 1: 先找到 CLI 入口注册位置

```bash
grep -r "add_typer\|report_app\|pipeline_app" huaqi_src/cli/ --include="*.py" -l
```

通常在 `huaqi_src/cli/main.py` 或 `huaqi_src/cli/app.py` 中。找到后仿照 `report.py` 的方式注册。

### Step 2: 写失败测试

```python
# tests/unit/cli/commands/test_world_command.py
import datetime
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from huaqi_src.cli.commands.world import world_app


runner = CliRunner()


def test_world_fetch_command_runs_pipeline():
    with patch("huaqi_src.cli.commands.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = True
        result = runner.invoke(world_app, ["fetch"])
        assert result.exit_code == 0
        MockPipeline.return_value.run.assert_called_once()


def test_world_fetch_command_with_date_option():
    with patch("huaqi_src.cli.commands.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = True
        result = runner.invoke(world_app, ["fetch", "--date", "2026-01-01"])
        assert result.exit_code == 0
        call_kwargs = MockPipeline.return_value.run.call_args
        assert datetime.date(2026, 1, 1) in (call_kwargs.args or ()) or \
               call_kwargs.kwargs.get("date") == datetime.date(2026, 1, 1)


def test_world_fetch_command_shows_error_on_failure():
    with patch("huaqi_src.cli.commands.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = False
        result = runner.invoke(world_app, ["fetch"])
        assert result.exit_code != 0 or "失败" in result.output or "未获取" in result.output
```

### Step 3: 运行测试确认失败

```bash
pytest tests/unit/cli/commands/test_world_command.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.cli.commands.world'`

### Step 4: 实现 world.py 命令

```python
# huaqi_src/cli/commands/world.py
import datetime
from typing import Optional

import typer

world_app = typer.Typer(help="世界新闻采集")


@world_app.command("fetch")
def fetch_cmd(
    date: Optional[str] = typer.Option(None, "--date", help="采集日期 YYYY-MM-DD，默认今天"),
):
    from huaqi_src.layers.data.world.pipeline import WorldPipeline

    target_date: Optional[datetime.date] = None
    if date:
        try:
            target_date = datetime.date.fromisoformat(date)
        except ValueError:
            typer.echo(f"日期格式错误: {date}，请使用 YYYY-MM-DD")
            raise typer.Exit(1)

    pipeline = WorldPipeline()
    success = pipeline.run(date=target_date)
    if not success:
        typer.echo("采集失败或未获取到任何文档")
        raise typer.Exit(1)
    typer.echo("采集完成")
```

### Step 5: 找到 CLI 主入口并注册 world_app

先查看主入口：
```bash
# 查看 CLI 入口文件（通常是 main.py 或 app.py）
```

仿照其他命令的注册方式，在对应文件加入：
```python
from huaqi_src.cli.commands.world import world_app
app.add_typer(world_app, name="world")
```

### Step 6: 运行测试确认通过

```bash
pytest tests/unit/cli/commands/test_world_command.py -v
```

预期：3 passed

### Step 7: 提交

```bash
git add huaqi_src/cli/commands/world.py tests/unit/cli/commands/test_world_command.py
git commit -m "feat: add huaqi world fetch CLI command"
```

---

## Task 9: ensure_initialized 集成 StartupJobRecovery

**Files:**
- Modify: `huaqi_src/cli/context.py`
- Create: `tests/unit/cli/test_context_recovery.py`

### Step 1: 写失败测试

```python
# tests/unit/cli/test_context_recovery.py
from unittest.mock import MagicMock, patch, call
import huaqi_src.cli.context as ctx_module


def test_ensure_initialized_triggers_startup_recovery(tmp_path):
    ctx_module._config = None
    ctx_module._personality = None
    ctx_module._hooks = None
    ctx_module._growth = None
    ctx_module._diary = None
    ctx_module._memory_store = None
    ctx_module._git = None
    ctx_module.DATA_DIR = None
    ctx_module.MEMORY_DIR = None

    with patch("huaqi_src.cli.context.require_data_dir", return_value=tmp_path), \
         patch("huaqi_src.cli.context.get_memory_dir", return_value=tmp_path / "memory"), \
         patch("huaqi_src.cli.context.init_config_manager"), \
         patch("huaqi_src.cli.context.PersonalityEngine"), \
         patch("huaqi_src.cli.context.GitAutoCommit"), \
         patch("huaqi_src.cli.context.HookManager"), \
         patch("huaqi_src.cli.context.GrowthTracker"), \
         patch("huaqi_src.cli.context.DiaryStore"), \
         patch("huaqi_src.cli.context.MarkdownMemoryStore"), \
         patch("huaqi_src.cli.context.StartupJobRecovery") as MockRecovery:

        ctx_module.ensure_initialized()

        MockRecovery.assert_called_once()
        MockRecovery.return_value.run.assert_called_once()
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/cli/test_context_recovery.py -v
```

预期：FAIL（`StartupJobRecovery` 未在 context.py 中被调用）

### Step 3: 修改 context.py

在 `ensure_initialized()` 末尾追加 StartupJobRecovery 调用：

在 `context.py` 顶部导入：
```python
# 在现有 import 区域末尾添加
from huaqi_src.scheduler.startup_recovery import StartupJobRecovery
from huaqi_src.scheduler.jobs import _DEFAULT_JOB_CONFIGS
```

在 `ensure_initialized()` 最末尾追加：
```python
    _run_startup_recovery()
```

在 `ensure_initialized` 之后新增函数：
```python
def _run_startup_recovery():
    try:
        from huaqi_src.config.paths import get_scheduler_db_path
        db_path = get_scheduler_db_path()
        recovery = StartupJobRecovery(
            data_dir=DATA_DIR,
            db_path=db_path,
            job_configs=_DEFAULT_JOB_CONFIGS,
        )
        recovery.run(notify_callback=_on_recovery_notify)
    except Exception as e:
        print(f"[Recovery] 启动检查失败: {e}")


def _on_recovery_notify(missed_jobs):
    names = "、".join(m.display_name for m in missed_jobs)
    console.print(f"[yellow]⚠️  发现 {len(missed_jobs)} 个任务未执行（{names}），正在后台补跑...[/yellow]")
```

### Step 4: 运行测试确认通过

```bash
pytest tests/unit/cli/test_context_recovery.py -v
```

预期：1 passed

### Step 5: 运行全部测试，确保没有回归

```bash
pytest tests/ -v
```

预期：全部 passed

### Step 6: 提交

```bash
git add huaqi_src/cli/context.py tests/unit/cli/test_context_recovery.py
git commit -m "feat: integrate StartupJobRecovery into ensure_initialized"
```

---

## Task 10: cli/commands/scheduler.py — 调度器管理命令

**Files:**
- Create: `huaqi_src/cli/commands/scheduler.py`
- Create: `tests/unit/cli/commands/test_scheduler_command.py`
- Modify: CLI 主入口（注册 scheduler_app）

### Step 1: 写失败测试

```python
# tests/unit/cli/commands/test_scheduler_command.py
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from huaqi_src.cli.commands.scheduler import scheduler_app

runner = CliRunner()


def test_scheduler_list_command():
    with patch("huaqi_src.cli.commands.scheduler._get_config_manager") as mock_cm:
        from huaqi_src.config.manager import AppConfig
        mock_cm.return_value.load_config.return_value = AppConfig()
        result = runner.invoke(scheduler_app, ["list"])
        assert result.exit_code == 0


def test_scheduler_enable_command():
    with patch("huaqi_src.cli.commands.scheduler._get_config_manager") as mock_cm:
        from huaqi_src.config.manager import AppConfig, SchedulerJobConfig
        config = AppConfig()
        mock_cm.return_value.load_config.return_value = config
        result = runner.invoke(scheduler_app, ["enable", "morning_brief"])
        assert result.exit_code == 0
        mock_cm.return_value.save_config.assert_called_once()


def test_scheduler_disable_command():
    with patch("huaqi_src.cli.commands.scheduler._get_config_manager") as mock_cm:
        from huaqi_src.config.manager import AppConfig, SchedulerJobConfig
        config = AppConfig()
        mock_cm.return_value.load_config.return_value = config
        result = runner.invoke(scheduler_app, ["disable", "morning_brief"])
        assert result.exit_code == 0
        mock_cm.return_value.save_config.assert_called_once()


def test_scheduler_set_cron_command():
    with patch("huaqi_src.cli.commands.scheduler._get_config_manager") as mock_cm:
        from huaqi_src.config.manager import AppConfig
        config = AppConfig()
        mock_cm.return_value.load_config.return_value = config
        result = runner.invoke(scheduler_app, ["set-cron", "morning_brief", "0 7 * * *"])
        assert result.exit_code == 0
        mock_cm.return_value.save_config.assert_called_once()
```

### Step 2: 运行测试确认失败

```bash
pytest tests/unit/cli/commands/test_scheduler_command.py -v
```

### Step 3: 实现 scheduler.py 命令

```python
# huaqi_src/cli/commands/scheduler.py
from typing import Optional
import typer
from rich.table import Table
from rich.console import Console

scheduler_app = typer.Typer(help="定时任务管理")
console = Console()


def _get_config_manager():
    from huaqi_src.config.manager import get_config_manager
    return get_config_manager()


@scheduler_app.command("list")
def list_cmd():
    from huaqi_src.scheduler.jobs import _DEFAULT_JOB_CONFIGS
    cm = _get_config_manager()
    config = cm.load_config()

    table = Table(title="定时任务配置")
    table.add_column("Job ID")
    table.add_column("显示名")
    table.add_column("启用")
    table.add_column("Cron")

    for job_id, defaults in _DEFAULT_JOB_CONFIGS.items():
        job_cfg = config.scheduler_jobs.get(job_id)
        enabled = job_cfg.enabled if job_cfg else True
        cron = (job_cfg.cron if job_cfg and job_cfg.cron else defaults["cron"])
        table.add_row(job_id, defaults["display_name"], "✓" if enabled else "✗", cron)

    console.print(table)


@scheduler_app.command("enable")
def enable_cmd(job_id: str):
    from huaqi_src.config.manager import SchedulerJobConfig
    from huaqi_src.scheduler.jobs import KNOWN_JOB_IDS
    if job_id not in KNOWN_JOB_IDS:
        typer.echo(f"未知任务: {job_id}")
        raise typer.Exit(1)
    cm = _get_config_manager()
    config = cm.load_config()
    existing = config.scheduler_jobs.get(job_id) or SchedulerJobConfig()
    config.scheduler_jobs[job_id] = SchedulerJobConfig(enabled=True, cron=existing.cron)
    cm.save_config()
    typer.echo(f"已启用: {job_id}")


@scheduler_app.command("disable")
def disable_cmd(job_id: str):
    from huaqi_src.config.manager import SchedulerJobConfig
    from huaqi_src.scheduler.jobs import KNOWN_JOB_IDS
    if job_id not in KNOWN_JOB_IDS:
        typer.echo(f"未知任务: {job_id}")
        raise typer.Exit(1)
    cm = _get_config_manager()
    config = cm.load_config()
    existing = config.scheduler_jobs.get(job_id) or SchedulerJobConfig()
    config.scheduler_jobs[job_id] = SchedulerJobConfig(enabled=False, cron=existing.cron)
    cm.save_config()
    typer.echo(f"已禁用: {job_id}")


@scheduler_app.command("set-cron")
def set_cron_cmd(job_id: str, cron: str):
    from huaqi_src.config.manager import SchedulerJobConfig
    from huaqi_src.scheduler.jobs import KNOWN_JOB_IDS
    if job_id not in KNOWN_JOB_IDS:
        typer.echo(f"未知任务: {job_id}")
        raise typer.Exit(1)
    cm = _get_config_manager()
    config = cm.load_config()
    existing = config.scheduler_jobs.get(job_id) or SchedulerJobConfig()
    config.scheduler_jobs[job_id] = SchedulerJobConfig(enabled=existing.enabled, cron=cron)
    cm.save_config()
    typer.echo(f"已更新 {job_id} cron: {cron}")
```

### Step 4: 注册到主入口（仿照 report.py 的方式）

### Step 5: 运行测试确认通过

```bash
pytest tests/unit/cli/commands/test_scheduler_command.py -v
```

预期：4 passed

### Step 6: 提交

```bash
git add huaqi_src/cli/commands/scheduler.py tests/unit/cli/commands/test_scheduler_command.py
git commit -m "feat: add huaqi scheduler CLI commands (list/enable/disable/set-cron)"
```

---

## 最终验证

所有任务完成后，运行完整测试套件：

```bash
pytest tests/ -v --tb=short
```

预期：新增测试全部 passed，无回归。

---

## 任务依赖顺序

```
Task 1 (WorldPipeline)
Task 2 (JobExecutionLog)
    └─ Task 3 (MissedJobScanner)
           └─ Task 6 (StartupJobRecovery)
                  └─ Task 9 (ensure_initialized 集成)
Task 4 (SchedulerJobConfig)
    └─ Task 5 (jobs.py 配置开关)
Task 1 → Task 7 (WorldProvider lazy 补采)
Task 1 → Task 8 (CLI world 命令)
Task 5 → Task 10 (CLI scheduler 命令)
```

从 Task 1、Task 2、Task 4 三条并行链路开始推进，互不阻塞。
