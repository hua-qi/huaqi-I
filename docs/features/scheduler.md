# 定时任务系统

## 概述

所有定时任务统一为 **Chat 任务**（prompt → ChatAgent），存储在 `{data_dir}/memory/scheduled_jobs.yaml`，支持通过 CLI 命令和 `huaqi chat` 对话进行增删改查，daemon 进程通过 mtime 轮询感知变更并自动重载。

---

## 设计思路

### 核心决策：取消"内置任务"概念

重构前，定时任务分为两类：
- **内置任务**：硬编码在 `jobs.py` 中，调用特定 Python 函数
- **Chat 任务**：prompt 字符串 → `ChatAgent.run()` 执行

重构后，统一为 Chat 任务。所有任务均为 `ScheduledJob(id, display_name, cron, enabled, prompt, output_dir?)`，通过 `_run_scheduled_job` 统一驱动 `ChatAgent`，无特殊代码路径。

**优势**：
- 任务定义纯数据化，可通过 Agent 对话直接管理（无需记忆 CLI 语法）
- 新增任务无需改代码，只需在 yaml 中追加一条记录
- output_dir 可选，支持将任务结果写入指定目录

### 跨进程同步

CLI 进程和 daemon 进程完全隔离，无法直接操作对方的 APScheduler 实例。解决方案：

- CLI/chat 修改 `scheduled_jobs.yaml` 后，只保证 yaml 文件已更新
- daemon 前台模式（`--foreground`）主循环每 5s 检查 yaml 的 mtime，检测到变更时调用 `register_jobs` 重载 APScheduler 任务

---

## 模块结构

```
huaqi_src/scheduler/
├── scheduled_job_store.py   # ScheduledJob 模型 + ScheduledJobStore
├── job_runner.py            # _run_scheduled_job — 统一执行入口
├── jobs.py                  # register_jobs — 从 store 同步到 APScheduler
├── manager.py               # SchedulerManager — APScheduler 封装
├── execution_log.py         # JobExecutionLog — SQLite 执行日志
├── missed_job_scanner.py    # MissedJobScanner — 遗漏任务扫描
└── startup_recovery.py      # StartupJobRecovery — 启动补跑

huaqi_src/agent/tools.py     # 6 个 scheduler 管理工具（@register_tool）
huaqi_src/cli/commands/scheduler.py  # huaqi scheduler 命令组
```

---

## 实现细节

### ScheduledJob 模型

```python
class ScheduledJob(BaseModel):
    id: str
    display_name: str
    cron: str           # 标准 5 段 cron，创建时校验
    enabled: bool = True
    prompt: str
    output_dir: Optional[str] = None   # 非空时结果写入该目录
```

存储路径：`{data_dir}/memory/scheduled_jobs.yaml`

首次启动自动写入 6 个预置任务：

| id | display_name | cron |
|----|-------------|------|
| `morning_brief` | 晨间简报 | `0 8 * * *` |
| `daily_report` | 日终复盘 | `0 23 * * *` |
| `weekly_report` | 周报 | `0 21 * * 0` |
| `quarterly_report` | 季报 | `0 22 28-31 3,6,9,12 *` |
| `learning_daily_push` | 学习推送 | `0 21 * * *` |
| `world_fetch` | 世界新闻采集 | `0 7 * * *` |

### ScheduledJobStore 并发安全

`add_job`/`update_job`/`remove_job` 在 `_locked()` 上下文管理器内完成完整的 read-modify-write 序列，消除并发修改窗口：

```python
@contextlib.contextmanager
def _locked(self):
    lock_path = self._path.with_suffix(".lock")
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)

def add_job(self, job: ScheduledJob):
    self._ensure_initialized()
    with self._locked():              # 锁住整个 read-modify-write
        jobs = self._load_raw()
        if any(j.id == job.id for j in jobs):
            raise ValueError(f"任务 ID 已存在: {job.id}")
        jobs.append(job)
        self._write_raw(_serialize_jobs(jobs))   # 原子写（.tmp + rename）
```

### _run_scheduled_job 执行流程

```
_run_scheduled_job(job_id, prompt, output_dir?, scheduled_at?, raise_on_error?)
    │
    ├── output_dir 非空 → 拼接 [系统] 前缀指令 + 文件路径注入到 prompt 头部
    │
    ├── ChatAgent().run(full_prompt)   ← 子线程异常通过 queue 传回主线程
    │
    ├── 成功 → execution_log.write_result(entry_id, "success")
    └── 异常 → print 错误；raise_on_error=True 时向上抛出
```

### register_jobs 幂等重载

```python
def register_jobs(manager: SchedulerManager, store: ScheduledJobStore):
    jobs = store.load_jobs()
    enabled_ids = {job.id for job in jobs if job.enabled}

    # 清理：移除所有不在 enabled_ids 中的 APScheduler 任务
    for apj in manager.scheduler.get_jobs():
        if apj.id not in enabled_ids:
            manager.scheduler.remove_job(apj.id)

    # 注册/更新启用任务（replace_existing=True，幂等）
    for job in jobs:
        if job.enabled:
            manager.add_cron_job(job.id, func=_run_scheduled_job, cron=job.cron, ...)
```

### daemon mtime 轮询

`daemon start --foreground` 主循环：

```python
_last_mtime = _yaml_path.stat().st_mtime if _yaml_path.exists() else 0.0
while True:
    time.sleep(5)
    if _yaml_path.exists():
        _mtime = _yaml_path.stat().st_mtime
        if _mtime != _last_mtime:
            _last_mtime = _mtime
            register_jobs(scheduler, _store)   # 重载任务
```

### MissedJobScanner 时区处理

使用标准库 `zoneinfo.ZoneInfo`，统一在目标时区内计算 fire_time，避免 `replace(tzinfo=None)` 裸剥除导致的时区偏差：

```python
tz = ZoneInfo(self.timezone)   # "Asia/Shanghai"
since_aware = since.replace(tzinfo=tz) if since.tzinfo is None else since.astimezone(tz)
# ... get_next_fire_time() 返回 aware datetime ...
next_local = next_time.astimezone(tz).replace(tzinfo=None)   # 转本地时区后剥除
```

### StartupJobRecovery 时钟回拨保护

```python
if now < last_opened:
    print(f"[Scheduler] 检测到系统时钟回拨，以保守估计重新扫描最近 24 小时")
    last_opened = now - datetime.timedelta(hours=24)
```

---

## 接口与使用

### CLI 命令

```bash
# 查看
huaqi scheduler list                               # 列出所有任务

# 增删改
huaqi scheduler add                                # 交互式添加任务
huaqi scheduler remove <job_id>                    # 删除任务
huaqi scheduler edit <job_id>                      # 编辑任务（交互）
huaqi scheduler edit <job_id> --clear-output-dir   # 清除 output_dir

# 启用/禁用
huaqi scheduler enable <job_id>
huaqi scheduler disable <job_id>

# 手动触发
huaqi scheduler run <job_id>                       # 立即执行一次
```

### 通过 Agent 对话管理

```
「帮我新增一个每周五晚上10点的周总结任务」
「把晨间简报改到早上7点」
「禁用世界新闻采集任务」
「帮我列出所有定时任务」
```

Agent 内置 6 个 scheduler 管理工具，对话即可完成 CRUD。

### 启动 daemon

```bash
huaqi daemon start --foreground   # 前台运行，实时感知 yaml 变更（推荐开发时使用）
huaqi daemon start                # 后台运行（不含 mtime 轮询）
```

---

## 相关文件

- `huaqi_src/scheduler/scheduled_job_store.py` — ScheduledJob 模型 + ScheduledJobStore
- `huaqi_src/scheduler/job_runner.py` — 统一执行入口
- `huaqi_src/scheduler/jobs.py` — register_jobs（动态加载 + 幂等重载）
- `huaqi_src/scheduler/manager.py` — APScheduler 封装（懒加载保护）
- `huaqi_src/scheduler/execution_log.py` — SQLite 执行日志
- `huaqi_src/scheduler/missed_job_scanner.py` — 遗漏任务扫描（zoneinfo 时区）
- `huaqi_src/scheduler/startup_recovery.py` — 启动补跑（时钟回拨保护）
- `huaqi_src/agent/tools.py` — scheduler 管理工具（6 个）
- `huaqi_src/cli/commands/scheduler.py` — `huaqi scheduler` 命令组
- `huaqi_src/cli/commands/system.py` — daemon start mtime 轮询
- `tests/unit/scheduler/test_jobs.py`
- `tests/unit/scheduler/test_missed_job_scanner.py`
- `tests/unit/scheduler/test_startup_recovery.py`
- `tests/unit/scheduler/test_learning_push.py`
- `tests/unit/agent/test_tool_registry.py`

---

**文档版本**: v1.0
**最后更新**: 2026-09-04
