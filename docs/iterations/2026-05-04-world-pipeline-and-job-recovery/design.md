# World Pipeline 与定时任务补跑机制

**Date:** 2026-05-04

## Context

项目现有的晨报/日报中包含"国际新闻"板块，由 `WorldProvider` 读取 `data/world/YYYY-MM-DD.md` 提供数据。然而这个文件从未被任何机制写入——`ContentPipeline` 采集的 X/RSS 数据只输出到小红书草稿（`data/drafts/`），与 `WorldNewsStorage` 完全断开。这是一个架构断层。

与此同时，定时任务系统（APScheduler）目前不记录执行历史，任务失败后仅打印日志，没有重试、降级或补跑机制。用户若长时间未启动守护进程，遗漏的任务会永久丢失。

本次设计目标：
1. 打通 Pipeline 采集 → 晨报国际新闻的数据链路（WorldPipeline）
2. 建立定时任务执行日志，支持 CLI 启动时自动感知并补跑遗漏任务
3. 支持用户通过配置文件控制定时任务的开关和执行时间

## Discussion

### WorldPipeline 方案选择

探讨了三种方案：

- **方案 A（独立 WorldPipeline）**：新建独立的采集流程，通过定时任务和 CLI 命令触发，写入 `WorldNewsStorage`
- **方案 B（ContentPipeline 扩展）**：在现有 ContentPipeline 跑完后附加写入 world 目录，但两套数据模型（`ContentItem` vs `HuaqiDocument`）混用，且小红书逻辑与新闻存储耦合
- **方案 C（MorningBriefAgent lazy fetch）**：晨报生成时即时采集，但会阻塞生成速度且日报无法复用数据

**最终选择方案 A**，职责独立、扩展性好，且 `WorldNewsFetcher` + `WorldNewsStorage` 已有完整实现，只缺调用入口。

### 新闻来源与领域

- 数据源：RSS 公开 Feed（免 API，最易实现），未来可扩展 X 源
- 覆盖领域：科技 & AI、金融 & 经济、地缘 & 政治

### 定时任务降级方案

探讨了三种降级策略：
- 晨报触发时 lazy 补采（无感知，但仅解决晨报问题）
- 回落到历史数据
- 优雅降级（显示"暂无数据"）

**WorldPipeline 降级**：采用 lazy 补采，在 `WorldProvider` 内实现，晨报生成时若文件不存在则即时触发一次采集，失败则晨报国际新闻段落显示"暂无数据"。

### 补跑机制的时间窗口

判断"任务是否遗漏"的时间窗口为**自上次打开 CLI 到当前时间**，而非仅看当天。系统需额外记录 `cli_last_opened` 时间戳，每次启动时更新。

多次遗漏同一任务（如用户 3 天未开 CLI）时，**全部补跑**，每个应触发时间点都有对应记录，历史可追溯。

### 补跑交互方式

用户打开 CLI 后：
- 立即显示欢迎界面，同时展示提示："⚠️ 发现 N 个任务未执行，正在后台补跑..."
- 后台异步线程执行补跑
- 全部完成后在对话流中插入通知："✅ 补跑完成：晨间简报 ✓  日报 ✓  学习推送 ✗（失败）"

### 定时任务配置

现有 `register_default_jobs()` 硬编码全量注册，无开关。`AppConfig` 中已有 `modules: Dict[str, bool]` 但过于扁平。

**最终方案**：在 `AppConfig` 中新增结构化的 `scheduler_jobs: Dict[str, SchedulerJobConfig]`，支持 `enabled` 开关和自定义 `cron` 表达式，空配置时默认全部启用（向后兼容）。

执行日志存储选择 **SQLite**（而非 JSON），复用现有 `scheduler.db`，并发写入安全，支持按 job_id + 时间范围索引查询，天花板高。

## Approach

1. **WorldPipeline**：独立采集流程，每天 07:00 定时触发，采集科技/金融/地缘三大领域 RSS，写入 `world/YYYY-MM-DD.md`。支持 `huaqi world fetch [--date]` 手动补跑。`WorldProvider` 内置 lazy 补采作为降级兜底。

2. **JobExecutionLog**：在 `scheduler.db` 新增 `job_execution_log` 表，每个 job handler 执行前写 `running`，成功写 `success`，失败写 `failed`。

3. **MissedJobScanner**：给定时间窗口 `[since, until]`，利用 APScheduler 的 `CronTrigger.get_next_fire_time()` 迭代计算每个 job 在窗口内的应触发时间点，逐一比对执行日志，返回无 `success` 记录的遗漏列表。

4. **StartupJobRecovery**：在 `ensure_initialized()` 末尾触发，读取 `cli_last_opened` → 扫描遗漏任务 → 更新时间戳 → 若有遗漏则展示提示并启动后台线程补跑 → 完成后通知对话流。

5. **SchedulerJobConfig**：`AppConfig` 新增配置字段，`register_default_jobs()` 读取后决定是否注册及使用哪条 cron，新增 `huaqi scheduler` 子命令管理开关。

## Architecture

### 数据流

```
07:00 world_fetch 定时任务
  └─ WorldPipeline.run()
       ├─ RSSSource × N（科技/金融/地缘）
       ├─ WorldNewsFetcher.fetch_all() → List[HuaqiDocument]
       └─ WorldNewsStorage.save() → world/YYYY-MM-DD.md

08:00 morning_brief 定时任务
  └─ MorningBriefAgent.run()
       └─ WorldProvider.get_context()
            ├─ 文件存在 → 直接读取
            └─ 文件不存在 → lazy 触发 WorldPipeline.run()
                  ├─ 成功 → 继续生成晨报
                  └─ 失败 → 返回 None，晨报显示"暂无数据"

CLI 启动
  └─ ensure_initialized()
       └─ StartupJobRecovery.run(notify_callback)
            ├─ 读 cli_last_opened
            ├─ MissedJobScanner.scan(last_opened, now)
            ├─ 更新 cli_last_opened = now
            ├─ 若有遗漏 → 打印提示
            └─ 后台线程补跑 → 完成后调用 notify_callback 注入对话流
```

### 核心组件

**JobExecutionLog**
```
SQLite 表：job_execution_log
  id           INTEGER PRIMARY KEY
  job_id       TEXT
  scheduled_at DATETIME
  status       TEXT  -- running / success / failed
  started_at   DATETIME
  finished_at  DATETIME
  error        TEXT

索引：(job_id, scheduled_at)

接口：
  write_start(job_id, scheduled_at) → entry_id
  write_result(entry_id, status, error=None)
  has_success(job_id, scheduled_at) → bool
  get_latest(job_id, since, until) → List[LogEntry]
```

**MissedJobScanner**
```python
class MissedJobScanner:
    def scan(since: datetime, until: datetime) -> List[MissedJob]

@dataclass
class MissedJob:
    job_id: str
    scheduled_at: datetime
    display_name: str
```

**SchedulerJobConfig**
```python
class SchedulerJobConfig(BaseModel):
    enabled: bool = True
    cron: Optional[str] = None  # None 使用系统默认值

class AppConfig(BaseModel):
    ...
    scheduler_jobs: Dict[str, SchedulerJobConfig] = Field(default_factory=dict)
```

对应配置示例：
```yaml
scheduler_jobs:
  morning_brief:
    enabled: true
    cron: "0 8 * * *"
  weekly_report:
    enabled: false
  world_fetch:
    enabled: true
    cron: "0 7 * * *"
```

### 新增/修改文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `layers/data/world/pipeline.py` | 新增 | WorldPipeline 主体 |
| `cli/commands/world.py` | 新增 | `huaqi world fetch` 命令 |
| `cli/commands/scheduler.py` | 新增 | enable / disable / list / set-cron |
| `scheduler/execution_log.py` | 新增 | JobExecutionLog SQLite 读写 |
| `scheduler/missed_job_scanner.py` | 新增 | 扫描遗漏任务 |
| `scheduler/startup_recovery.py` | 新增 | 启动补跑编排 |
| `scheduler/jobs.py` | 修改 | 接入配置开关 + 写执行日志 |
| `config/manager.py` | 修改 | 新增 SchedulerJobConfig + scheduler_jobs 字段 |
| `cli/context.py` | 修改 | ensure_initialized() 末尾触发 StartupJobRecovery |
| `cli/chat.py` | 修改 | 补跑完成通知注入对话流 |
| `layers/capabilities/reports/providers/world.py` | 修改 | lazy 补采逻辑 |
