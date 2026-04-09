# 定时任务深度审查 - 新增漏洞清单

> 审查时间：2026-09-04  
> 范围：scheduler 模块全量代码 + agent tools + cli commands

---

## 高严重度

### Bug A：startup_recovery 的 raise_on_error 实际无效

**文件：** `huaqi_src/scheduler/job_runner.py`

**问题：** `_run_scheduled_job` 内部 `try/except` 已吞掉异常，`if raise_on_error: raise` 依赖的 `raise` 是在 `except` 块内的 `raise`（重新抛出当前异常），逻辑正确，但 `startup_recovery` 调用时传了 `raise_on_error=True`，Agent 内部报错能否真的向上传播，取决于 `ChatAgent.run()` 是否会把内部异常抛出，还是自己吃掉。需要确认 `ChatAgent.run()` 的异常传播行为，确保链路完整。

**影响：** execution_log 可能永远记录 success，漏执行任务被标记为已完成后不再重跑。

**修复建议：** 审查 `ChatAgent.run()` 是否会抛出异常；若不抛出，改为返回执行状态（成功/失败/错误消息）。

---

### Bug B：scheduled_job_store 的并发修改存在数据丢失窗口

**文件：** `huaqi_src/scheduler/scheduled_job_store.py`

**问题：** 文件锁只保护 `_write_raw`（写入阶段），但 `load_jobs()` → 修改 → `save_jobs()` 这一序列不在锁的范围内：

```
进程 A: load_jobs()（读到 10 个任务）
进程 B: load_jobs()（读到 10 个任务）
进程 A: add_job → 写入 11 个任务（加锁，成功）
进程 B: add_job → 写入 11 个任务（加锁，成功）← 丢失了 A 的修改
```

所有 `add_job`、`update_job`、`remove_job` 均有此问题。

**修复建议：** 将 `load_jobs()` 也纳入文件锁范围，即在写操作中锁住整个 read-modify-write 序列。

---

### Bug C：daemon stop/status 命令意外初始化 AsyncIOScheduler

**文件：** `huaqi_src/cli/commands/system.py`

**问题：** `daemon_command_handler` 顶部直接调用 `scheduler = get_scheduler_manager()`，继而访问 `scheduler.is_running()`，会触发 `@property scheduler` 的懒加载，创建 `AsyncIOScheduler` 实例并绑定事件监听器，产生不必要的资源开销。

执行 `huaqi daemon stop` 或 `huaqi daemon status` 时：
- 会创建一个从未启动过的 `AsyncIOScheduler`
- `is_running()` 返回 False（符合预期），但实例已被创建
- 如果紧接着执行 `huaqi daemon start`，行为符合预期，但这是巧合，不是设计

**修复建议：** `status`/`stop` 分支通过 PID 文件或进程检查来判断 daemon 状态，不触发 `get_scheduler_manager()` 的懒加载。

---

### Bug D：CLI/chat 操作后 _sync_to_scheduler 实际不起作用（进程隔离）

**文件：** `huaqi_src/cli/commands/scheduler.py`，`huaqi_src/agent/tools.py`

**问题：** `_sync_to_scheduler` 和 `_sync_scheduler_after_tool` 调用 `get_scheduler_manager()` 创建的是**当前进程的新实例**，与 daemon 后台进程中的 APScheduler 实例完全隔离，无法跨进程同步。

结果：
- 用户通过 `huaqi scheduler add` 或 `huaqi chat` 新增任务 → yaml 写入成功，daemon 进程中的 APScheduler 不知道 → **任务不会触发**
- 用户删除/禁用任务 → daemon 中的旧任务**仍然会继续触发**

**修复建议（二选一）：**
1. **SIGHUP 信号**：daemon 启动时注册 SIGHUP 处理器，收到信号后重载任务；CLI/chat 操作后写 PID 文件并发送 SIGHUP
2. **定期轮询**：daemon 内起一个线程，每 N 秒检查 yaml 的 mtime，有变化则调用 `register_jobs`

---

## 中严重度

### Bug E：文件锁无超时，进程崩溃可能造成死锁

**文件：** `huaqi_src/scheduler/scheduled_job_store.py` `save_jobs()`

**问题：** 使用 `fcntl.LOCK_EX`（阻塞式独占锁），没有超时机制。若持锁进程崩溃，OS 会在文件描述符关闭时自动释放锁，但 `context manager` + `try/finally` 场景下，若 `open()` 本身成功但随后进程被 `kill -9` 杀死，锁文件可能残留。

另外 `fcntl` 在 Windows 上不可用（`ImportError`）。

**修复建议：** 写入改为原子操作（先写 `.tmp` 再 `rename`），配合 `fcntl` 锁；或引入 `filelock` 库支持超时和跨平台。

---

### Bug F：register_jobs 中 yaml_job_ids 包含禁用任务，导致逻辑冗余

**文件：** `huaqi_src/scheduler/jobs.py` `register_jobs()`

**问题：** 第一阶段"清理 APScheduler 中不在 yaml 里的任务"用 `yaml_job_ids`（包含禁用任务），导致禁用任务被"保护"不被清理；第二阶段再单独循环去 `remove_job` 删除禁用任务。两段逻辑目标相同但路径冗余，容易产生误解。

**修复建议：** 统一使用 `enabled_ids`，第一阶段直接清理所有不在 `enabled_ids` 中的 APScheduler 任务，去掉第二阶段的禁用任务单独删除循环。

---

### Bug G：时区不一致导致 missed_job_scanner 可能漏检

**文件：** `huaqi_src/scheduler/missed_job_scanner.py` `_get_fire_times()`

**问题：** `since` 和 `until` 是 naive datetime，`CronTrigger.get_next_fire_time()` 返回 aware datetime（带时区），通过 `replace(tzinfo=None)` 直接剥除时区信息，而非转换为本地时间。若系统时区与 `self.timezone`（`Asia/Shanghai`）不一致，会导致计算出的 fire_time 偏差最多数小时，进而误判任务是否被漏执行。

**修复建议：** 统一在 `Asia/Shanghai` 时区内计算，`since`/`until` 传入前用 `pytz.localize()` 赋予时区信息。

---

### Bug H：_run_scheduled_job 中 output_dir 注入依赖 Agent 自觉

**文件：** `huaqi_src/scheduler/job_runner.py`

**问题：** 通过字符串拼接在 prompt 头部注入写文件指令，但 LLM 可能不遵守，也可能理解偏差（"写入目录"vs"写入文件"）。无法验证 Agent 是否真的调用了 `write_file_tool`。

**修复建议：** Agent 执行完成后检查目标文件是否存在；或通过 `ChatAgent` 的 system prompt 机制传递而非拼接到 user prompt 头部。

---

### Bug I：startup_recovery 不处理系统时钟回拨

**文件：** `huaqi_src/scheduler/startup_recovery.py`

**问题：** 若 NTP 同步导致系统时钟回拨，`now < last_opened`，`scanner.scan()` 范围为负数区间，返回空列表，这期间真正漏执行的任务不会被补跑。

**修复建议：** 检测到 `now < last_opened` 时打印警告，并将 `last_opened` 重置为 `now - timedelta(hours=X)` 作为保守估计重新扫描。

---

## 低严重度

### Bug J：load_jobs 每次调用都全量读取和解析 yaml

**文件：** `huaqi_src/scheduler/scheduled_job_store.py`

**问题：** `get_job`、`add_job`、`update_job`、`remove_job` 都调用 `load_jobs()`，每次都做完整 I/O + yaml 解析 + Pydantic 校验。高频场景下（如 startup_recovery 遍历多个漏执行任务）有不必要的重复开销。

**修复建议：** 增加基于文件 mtime 的内存缓存，或在单次操作内复用已加载的结果。

---

### Bug K：execution_log 缺少执行时长和自动清理机制

**文件：** `huaqi_src/scheduler/execution_log.py`

**问题：** 表结构缺少 `duration_seconds` 字段，无法统计任务执行耗时；也没有按时间自动清理老记录的机制，长期运行后表会无限增长。

**修复建议：** 增加 `duration_seconds` 字段（`write_result` 时计算），以及定期 `DELETE WHERE started_at < NOW() - 90 days` 的清理任务。

---

### Bug L：cron 校验错误消息不友好

**文件：** `huaqi_src/cli/commands/scheduler.py`，`huaqi_src/agent/tools.py`

**问题：** cron 校验在 Pydantic validator 层抛出 `ValueError`，用户看到的是底层技术错误消息。CLI 的 `prompt` 模式下，用户输错 cron 后直接退出，没有重试机会。

**修复建议：** CLI `add` 命令中单独校验 cron，校验失败时打印友好提示并允许重新输入。

---

### Bug M：任务缺少幂等性保护，可能重复执行

**文件：** `huaqi_src/scheduler/job_runner.py`

**问题：** 若 APScheduler 触发任务和用户手动 `huaqi scheduler run` 在极短时间内并发执行，同一任务会被执行两次。`execution_log` 中会有两条记录，但没有防止并发执行的机制。

**修复建议：** 执行前检查 `execution_log` 中是否有 `status=running` 的同 `job_id` 记录，有则跳过（或等待）。

---

## 总览

| ID | 文件 | 严重度 | 一句话描述 |
|----|------|--------|-----------|
| A  | job_runner.py | 高 | raise_on_error 链路需验证 ChatAgent 异常传播 |
| B  | scheduled_job_store.py | 高 | 读-改-写序列无锁，并发时数据丢失 |
| C  | system.py | 高 | stop/status 命令意外初始化 AsyncIOScheduler |
| D  | scheduler.py / tools.py | 高 | 跨进程同步无效，yaml 写入后 daemon 不感知 |
| E  | scheduled_job_store.py | 中 | 文件锁无超时，fcntl 不跨平台 |
| F  | jobs.py | 中 | register_jobs 中禁用任务清理逻辑冗余 |
| G  | missed_job_scanner.py | 中 | 时区剥除方式错误，可能漏检 |
| H  | job_runner.py | 中 | output_dir 注入依赖 LLM 自觉，无法验证 |
| I  | startup_recovery.py | 中 | 时钟回拨时漏检任务 |
| J  | scheduled_job_store.py | 低 | load_jobs 无缓存，高频调用有重复 I/O |
| K  | execution_log.py | 低 | 缺少 duration 字段和自动清理 |
| L  | scheduler.py / tools.py | 低 | cron 错误消息不友好，无重试 |
| M  | job_runner.py | 低 | 并发执行时缺少幂等性保护 |
