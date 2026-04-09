# 定时任务重构 - 功能遗漏清单

## 背景

本文档记录当前定时任务重构（`scheduled_job_store` 方案）的已知功能遗漏，供后续迭代补齐。

---

## 遗漏一：chat 操作任务后未同步到运行中的 APScheduler

**优先级：高**

**问题描述：**

用户通过 `huaqi chat` 调用 `add_scheduled_job_tool` / `remove_scheduled_job_tool` / `enable_scheduled_job_tool` 等工具时，变更只写入了 `scheduled_jobs.yaml`，**不会同步到已在运行中的 APScheduler 实例**。

- 新增任务 → yaml 已写入，但 APScheduler 不知道，**不会按时触发**
- 删除/禁用任务 → yaml 已更新，但 APScheduler 仍持有旧 job，**会继续触发**

只有 daemon 重启后 `register_jobs()` 重新加载，才会生效。

**期望行为：** chat 工具操作后应同步调用 `register_jobs(scheduler, store)` 或对应的 `scheduler.add_cron_job` / `scheduler.remove_job`。

**影响范围：**
- `huaqi_src/agent/tools.py` 中的所有 `*_scheduled_job_tool` 函数

---

## 遗漏二：CLI scheduler 命令操作后未同步到运行中的 APScheduler

**优先级：高**

**问题描述：** 与遗漏一相同，`huaqi scheduler add/remove/disable` 等 CLI 命令只写 yaml，不通知 daemon 进程的 APScheduler 实例。

daemon 和 CLI 是两个独立进程，yaml 是共享状态，但 APScheduler 状态在 daemon 进程内存中。

**期望行为：** 方案一，daemon 进程定期（如每分钟）轮询 yaml 变更并 reload；方案二，通过 IPC（如 socket/文件锁信号）通知 daemon 重载任务。

**影响范围：**
- `huaqi_src/cli/commands/scheduler.py` 所有写操作命令

---

## 遗漏三：`huaqi scheduler add` 的 output_dir prompt 行为异常

**优先级：中**

**问题描述：**

```python
output_dir: Optional[str] = typer.Option(None, "--output-dir", prompt="输出目录（回车跳过）"),
```

`typer.Option` 设置了 `prompt` 时，若用户直接回车，得到的是空字符串 `""`，后续用 `output_dir or None` 转换为 `None`，逻辑上可以工作，但：

1. 用户无法通过 CLI 将已有 `output_dir` **清空**为 `None`（`edit` 命令同样存在此问题）
2. 交互体验不够清晰，用户不知道"回车跳过"和"输入空值"的区别

**期望行为：** 明确区分"跳过"（不修改）和"清空"（设为 None），或提供 `--clear-output-dir` 选项。

---

## 遗漏四：cron 表达式未做校验

**优先级：中**

**问题描述：** `add`/`edit` 命令和 chat 工具均未对用户输入的 cron 表达式做格式校验。非法 cron（如 `0 25 * * *`、`abc`）会在 `manager.add_cron_job` 调用时才报错，错误信息不友好。

**期望行为：** 在 `ScheduledJob` 的 Pydantic validator 或 `ScheduledJobStore.add_job` 中提前用 `CronTrigger.from_crontab()` 校验，失败时返回清晰错误。

**影响范围：**
- `huaqi_src/scheduler/scheduled_job_store.py` `ScheduledJob` 模型

---

## 遗漏五：`update_scheduled_job_tool` 无法清空 output_dir

**优先级：低**

**问题描述：**

```python
if output_dir:
    job.output_dir = output_dir
```

用户通过 chat 说"取消这个任务的输出目录"时，Agent 会传 `output_dir=""`，但因为 `if output_dir` 判断为假，**实际上不会清空**，静默失败。

**期望行为：** 引入特殊标记（如 `output_dir="__clear__"`）或用 `Optional` 参数区分"未传"和"主动清空"。

---

## 遗漏六：`scheduled_jobs.yaml` 无并发写保护

**优先级：低**

**问题描述：** `save_jobs` 直接覆盖写文件，若 daemon 进程和 CLI 进程同时写，可能导致文件损坏或数据丢失。

**期望行为：** 写入前使用文件锁（如 `fcntl.flock` 或 `filelock` 库）。

---

## 遗漏七：`scheduled_jobs.yaml` 中的 `output_dir: null` 序列化问题

**优先级：低**

**问题描述：** Pydantic `model_dump()` 会将 `output_dir=None` 序列化为 `output_dir: null` 写入 yaml，这是合法的，但初始化时 `_DEFAULT_JOBS` 中也显式写了 `"output_dir": None`，会被 yaml.dump 序列化为 `output_dir: null`，导致文件略显冗长。

影响不大，但可以在 `_write_raw` 时过滤掉 `null` 字段。

---

## 遗漏八：`test_tool_registry_contains_all_existing_tools` 未覆盖新增工具

**优先级：低**

**问题描述：** `tests/unit/agent/test_tool_registry.py` 中的 `test_tool_registry_contains_all_existing_tools` 测试可能未包含对新增的 8 个工具（`write_file_tool`、`read_file_tool`、6 个 scheduler 管理工具）的断言，需要确认。

**影响范围：**
- `tests/unit/agent/test_tool_registry.py`
