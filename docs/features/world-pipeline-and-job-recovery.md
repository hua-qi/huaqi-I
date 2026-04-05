# World Pipeline 与定时任务补跑机制

## 概述

打通 RSS 世界新闻采集到晨报国际新闻的数据链路，并建立定时任务执行日志与 CLI 启动补跑机制，确保长期离线或异常退出后定时任务不丢失。

---

## 设计思路

### 问题

1. **数据链路断裂**：`WorldProvider` 依赖 `{data_dir}/world/YYYY-MM-DD.md` 存在才能为晨报提供国际新闻上下文，但该文件没有独立的定时采集流程驱动写入。
2. **任务静默丢失**：APScheduler 仅在进程存活期间执行定时任务。进程重启或长期未打开 CLI，期间应执行的任务会静默跳过，无法追溯。

### 解决方案

```
WorldPipeline          ← 独立采集流程（Task 1）
    ↓ 定时调用
jobs.py world_fetch    ← 每日 07:00 定时任务（Task 5）
    ↓ 执行记录
JobExecutionLog        ← SQLite 执行日志（Task 2）
    ↓ 扫描
MissedJobScanner       ← 遗漏任务检测（Task 3）
    ↓ 编排
StartupJobRecovery     ← CLI 启动时补跑（Task 6）
    ↓ 触发
ensure_initialized()   ← 每次 CLI 启动时调用（Task 9）
```

`WorldProvider` 额外增加 lazy 补采兜底（Task 7）：若报告生成时当天文件仍缺失，自动触发一次 `WorldPipeline.run()`，不影响报告的正常生成流程。

---

## 模块结构

```
huaqi_src/
├── layers/data/world/
│   └── pipeline.py                  # WorldPipeline — 独立采集流程
├── layers/capabilities/reports/providers/
│   └── world.py                     # WorldProvider — 含 lazy 补采
├── scheduler/
│   ├── execution_log.py             # JobExecutionLog — SQLite 执行日志
│   ├── missed_job_scanner.py        # MissedJobScanner — 遗漏任务扫描
│   ├── startup_recovery.py          # StartupJobRecovery — 启动补跑
│   └── jobs.py                      # 新增 world_fetch 任务 + 配置开关支持
├── config/
│   └── manager.py                   # AppConfig 新增 SchedulerJobConfig
└── cli/
    ├── context.py                   # ensure_initialized 集成补跑
    └── commands/
        ├── world.py                 # huaqi world fetch 命令
        └── scheduler.py            # huaqi scheduler 命令组
```

---

## 实现细节

### WorldPipeline

```python
# huaqi_src/layers/data/world/pipeline.py
class WorldPipeline:
    def __init__(self, data_dir: Optional[Path] = None): ...

    def run(self, date: Optional[datetime.date] = None) -> bool:
        # 从 DEFAULT_RSS_FEEDS 抓取 → WorldNewsFetcher → WorldNewsStorage
        # 成功返回 True，无文档或异常返回 False
```

默认 RSS 源（可扩展）：
- BBC 科技：`https://feeds.bbci.co.uk/news/technology/rss.xml`
- CNN 财经：`https://rss.cnn.com/rss/money_news_international.rss`
- 路透社国际：`https://feeds.reuters.com/reuters/worldNews`

### JobExecutionLog

基于 SQLite 标准库，表结构：

```sql
CREATE TABLE job_execution_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,   -- ISO 格式
    status       TEXT NOT NULL DEFAULT 'running',  -- running / success / failed
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    error        TEXT
);
CREATE INDEX idx_job_scheduled ON job_execution_log (job_id, scheduled_at);
```

主要方法：
- `write_start(job_id, scheduled_at) -> int` — 创建 running 记录，返回 entry_id
- `write_result(entry_id, status, error?)` — 更新为 success/failed
- `has_success(job_id, scheduled_at) -> bool` — 判断某次调度是否已成功
- `get_latest(job_id, since, until) -> List[LogEntry]` — 查询历史记录

### MissedJobScanner

通过 `CronTrigger.from_crontab(cron).get_next_fire_time()` 枚举时间窗口内应触发的时间点，逐一查 `JobExecutionLog.has_success()`，未成功的即为遗漏：

```python
scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
missed: List[MissedJob] = scanner.scan(since, until)
# MissedJob: job_id, scheduled_at, display_name
```

**注意**：APScheduler `get_next_fire_time()` 返回 timezone-aware datetime，需转为 naive 并以 `+1s` 推进 `current`，否则会陷入无限循环。

### StartupJobRecovery

持久化 `{data_dir}/scheduler_meta.json`：

```json
{"cli_last_opened": "2026-05-03T10:00:00"}
```

启动时流程：
1. 读取 `cli_last_opened`
2. 写入当前时间
3. 若 `last_opened` 存在，扫描 `[last_opened, now]` 遗漏任务
4. 调用 `notify_callback(missed_jobs)` 通知用户
5. 启动后台线程依次补跑遗漏任务，写入执行日志

### SchedulerJobConfig

```python
class SchedulerJobConfig(BaseModel):
    enabled: bool = True
    cron: Optional[str] = None   # None = 使用默认 cron

class AppConfig(BaseModel):
    ...
    scheduler_jobs: Dict[str, SchedulerJobConfig] = Field(default_factory=dict)
```

`register_default_jobs(manager, config?)` 读取配置：
- `enabled=False` → 跳过注册
- `cron` 有值 → 使用自定义 cron，否则使用默认值

### WorldProvider lazy 补采

```python
def get_context(self, report_type, date_range) -> str | None:
    world_file = self._data_dir / "world" / f"{today}.md"
    if not world_file.exists():
        world_file = self._lazy_fetch(today)   # 触发 WorldPipeline
    if world_file is None or not world_file.exists():
        return None
    ...
```

---

## 接口与使用

### CLI 命令

```bash
# 手动触发采集
huaqi world fetch                  # 采集今天的世界新闻
huaqi world fetch --date 2026-01-01  # 采集指定日期

# 定时任务管理
huaqi scheduler list               # 查看所有任务配置（启用状态、cron）
huaqi scheduler enable morning_brief   # 启用任务
huaqi scheduler disable world_fetch    # 禁用任务
huaqi scheduler set-cron morning_brief "0 7 * * *"  # 自定义触发时间
```

### 默认任务时间表

| Job ID | 默认 Cron | 说明 |
|--------|----------|------|
| `morning_brief` | `0 8 * * *` | 每日 08:00 晨间简报 |
| `daily_report` | `0 23 * * *` | 每日 23:00 日终复盘 |
| `weekly_report` | `0 21 * * 0` | 每周日 21:00 周报 |
| `quarterly_report` | `0 22 28-31 3,6,9,12 *` | 每季末月底 22:00 季报 |
| `learning_daily_push` | `0 21 * * *` | 每日 21:00 学习推送 |
| `world_fetch` | `0 7 * * *` | 每日 07:00 世界新闻采集 |

### Python API

```python
from huaqi_src.layers.data.world.pipeline import WorldPipeline

pipeline = WorldPipeline(data_dir=Path("/your/data"))
success = pipeline.run(date=datetime.date.today())
```

```python
from huaqi_src.scheduler.startup_recovery import StartupJobRecovery
from huaqi_src.scheduler.jobs import _DEFAULT_JOB_CONFIGS

recovery = StartupJobRecovery(
    data_dir=data_dir,
    db_path=data_dir / "scheduler.db",
    job_configs=_DEFAULT_JOB_CONFIGS,
)
recovery.run(notify_callback=lambda missed: print(f"补跑 {len(missed)} 个任务"))
```

---

## 相关文件

- `huaqi_src/layers/data/world/pipeline.py` — WorldPipeline
- `huaqi_src/layers/capabilities/reports/providers/world.py` — WorldProvider（含 lazy 补采）
- `huaqi_src/scheduler/execution_log.py` — JobExecutionLog
- `huaqi_src/scheduler/missed_job_scanner.py` — MissedJobScanner
- `huaqi_src/scheduler/startup_recovery.py` — StartupJobRecovery
- `huaqi_src/scheduler/jobs.py` — 定时任务注册（含 world_fetch、配置开关）
- `huaqi_src/config/manager.py` — SchedulerJobConfig
- `huaqi_src/cli/context.py` — ensure_initialized 集成
- `huaqi_src/cli/commands/world.py` — world fetch 命令
- `huaqi_src/cli/commands/scheduler.py` — scheduler 命令组
- `tests/unit/layers/data/world/test_pipeline.py` — 5 cases
- `tests/unit/layers/data/world/test_world_provider.py` — 4 cases
- `tests/unit/scheduler/test_execution_log.py` — 6 cases
- `tests/unit/scheduler/test_missed_job_scanner.py` — 5 cases
- `tests/unit/scheduler/test_startup_recovery.py` — 5 cases
- `tests/unit/scheduler/test_jobs.py` — 6 cases（含新增 4 cases）
- `tests/unit/config/test_scheduler_job_config.py` — 5 cases
- `tests/unit/cli/test_context_recovery.py` — 1 case
- `tests/unit/cli/commands/test_world_command.py` — 3 cases
- `tests/unit/cli/commands/test_scheduler_command.py` — 4 cases

---

**文档版本**: v1.0
**最后更新**: 2026-05-04
