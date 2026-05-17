# 定时任务重构 - 逻辑 Bug 清单

## 背景

本文档记录当前定时任务重构代码中存在的逻辑 Bug，按严重程度排序。

---

## Bug 1：startup_recovery 补跑漏执行任务时，异常不会被 execution_log 捕获

**严重程度：高**

**位置：** `huaqi_src/scheduler/startup_recovery.py` `_run_missed_jobs()`

**问题代码：**

```python
try:
    _run_scheduled_job(job.id, job.prompt, job.output_dir)
    log.write_result(entry_id, "success")
except Exception as e:
    log.write_result(entry_id, "failed", error=str(e))
```

**问题：** `_run_scheduled_job` 内部已经 `try/except` 吞掉了所有异常：

```python
def _run_scheduled_job(job_id, prompt, output_dir):
    try:
        agent = ChatAgent()
        agent.run(full_prompt)
    except Exception as e:
        print(f"[Scheduler] 任务 {job_id} 执行失败: {e}")  # 异常被吞掉
```

因此 `startup_recovery` 的外层 `except` **永远不会触发**，`log.write_result(entry_id, "failed", ...)` 永远不会被调用，所有任务最终都会被记录为 `success`，即使实际执行失败。

**修复建议：** `_run_scheduled_job` 应将异常向上抛出（或返回状态），由调用方决定是否记录失败。可以拆分为两个版本，或增加 `raise_on_error: bool` 参数。

---

## Bug 2：register_jobs 中"清理未知任务"逻辑反了

**严重程度：高**

**位置：** `huaqi_src/scheduler/jobs.py` `register_jobs()`

**问题代码：**

```python
def register_jobs(manager: SchedulerManager, store: ScheduledJobStore):
    jobs = store.load_jobs()
    registered_ids = {job.id for job in jobs}   # ← 变量名有误导性

    try:
        existing = manager.scheduler.get_jobs()
        for apj in existing:
            if apj.id not in registered_ids:    # ← 清理 yaml 中不存在的 APScheduler job
                manager.scheduler.remove_job(apj.id)
    except Exception:
        pass
```

`registered_ids` 实际上是"yaml 中所有任务的 id"，不是"已注册到 APScheduler 的 id"。  
逻辑本身是对的（清理 APScheduler 中多余的、yaml 里不存在的任务），但**变量命名严重误导**，极易引发维护时的理解错误。

此外，禁用的任务（`enabled=False`）被包含在 `registered_ids` 中，会**保护禁用任务不被清理**，而后续代码又单独去 `remove_job`，产生冗余操作。

**修复建议：** 将变量改名为 `yaml_job_ids`，并在清理阶段直接用 `enabled_ids` 决定保留哪些任务。

---

## Bug 3：`cli/__init__.py` 中 daemon 启动时 APScheduler 提前 start

**严重程度：高**

**位置：** `huaqi_src/cli/__init__.py`

**问题代码：**

```python
if is_data_dir_set() and ctx.invoked_subcommand == "daemon":
    ...
    register_jobs(_scheduler, _store)
    _scheduler.start()  # ← 在命令真正执行前就 start 了
```

这段代码在 `@app.callback` 阶段执行，此时 `daemon` 子命令还没有运行。如果用户执行的是 `huaqi daemon stop` 或 `huaqi daemon status`，APScheduler 仍然会被启动，造成：

1. `stop` 命令：先意外启动调度器，再立刻关闭，浪费资源且行为不符预期
2. `status` 命令：会显示"运行中"（因为刚被这里启动了），结果不准确

**正确位置：** 应该只在 `system.py` 的 `daemon_command_handler(action="start")` 分支中启动，`cli/__init__.py` 不应做任何 scheduler 操作。

---

## Bug 4：`ScheduledJob` 是 Pydantic 模型但被当作可变对象修改

**严重程度：中**

**位置：** `huaqi_src/cli/commands/scheduler.py` `edit_cmd` / `enable_cmd` / `disable_cmd`

**问题代码：**

```python
job = store.get_job(job_id)
job.enabled = True   # ← 直接修改 Pydantic model 的字段
store.update_job(job)
```

Pydantic v2 默认模型是**不可变的**（`model_config` 默认 `frozen=False`，所以此处实际可以修改），但这是依赖了 Pydantic 的默认行为。若未来 `ScheduledJob` 加上 `model_config = ConfigDict(frozen=True)`，这里会静默失败或报错。

**修复建议：** 使用 `job.model_copy(update={"enabled": True})` 替代直接赋值，更符合 Pydantic 的使用规范。

---

## Bug 5：`add_cmd` 的 `output_dir` prompt 无法区分"跳过"和空字符串

**严重程度：中**

**位置：** `huaqi_src/cli/commands/scheduler.py` `add_cmd`

**问题代码：**

```python
output_dir: Optional[str] = typer.Option(None, "--output-dir", prompt="输出目录（回车跳过）"),
```

`typer` 在 `prompt` 模式下，用户直接回车会得到 `None`（Option 默认值），但用户输入空格再回车会得到 `" "`，后续 `output_dir or None` 不会将空格字符串转为 `None`，导致 `output_dir=" "` 被存入 yaml。

**修复建议：** 改为 `output_dir = (output_dir or "").strip() or None`。

---

## Bug 6：`_run_scheduled_job` 中 output_dir 注入方式过于脆弱

**严重程度：中**

**位置：** `huaqi_src/scheduler/jobs.py` `_run_scheduled_job()`

**问题代码：**

```python
if output_dir:
    full_prompt += f"\n\n请将结果写入目录：{output_dir}"
```

这里通过字符串拼接将 `output_dir` 注入 prompt，依赖 Agent 理解并调用 `write_file_tool`。但：

1. Agent 不一定会遵守（LLM 输出不可控）
2. `write_file_tool` 并不是"写入目录"而是"写入文件"，Agent 需要自己构造完整文件名
3. prompt 末尾追加指令的优先级低于原始 prompt，可能被 Agent 忽略

**修复建议：** prompt 注入改为 system prompt 或以更结构化的方式传递，并明确指定文件名规则（如 `{output_dir}/{job_id}_{date}.md`）。

---

## Bug 7：`startup_recovery` 在 `_run_missed_jobs` 中重复加载 store

**严重程度：低**

**位置：** `huaqi_src/scheduler/startup_recovery.py` `_run_missed_jobs()`

**问题：** 每次补跑漏执行任务都会重新实例化 `ScheduledJobStore` 并调用 `load_jobs()`（即读一次 yaml），与 `run()` 方法中构建 `job_configs` 时的加载是重复的。虽然不影响正确性，但增加了 I/O 且两次加载之间可能存在状态不一致（yaml 被修改）。

**修复建议：** 在 `run()` 中加载 jobs 后直接传给 `_run_missed_jobs`，避免重复加载。

---

## Bug 8：`register_jobs` 在 APScheduler 未启动时调用 `get_jobs()` 可能抛出异常被静默吞掉

**严重程度：低**

**位置：** `huaqi_src/scheduler/jobs.py` `register_jobs()`

**问题代码：**

```python
try:
    existing = manager.scheduler.get_jobs()
    ...
except Exception:
    pass   # ← 任何异常都被吞掉
```

裸 `except Exception: pass` 会吞掉所有错误（包括配置错误、数据库损坏等），使问题难以排查。

**修复建议：** 仅捕获 `JobLookupError` 等 APScheduler 特定异常，或至少 `except Exception as e: print(f"[Scheduler] 清理任务失败: {e}")`。
