# ADR-007: 定时任务统一为 Chat 任务，取消内置函数任务

**状态**: 已采纳
**日期**: 2026-09-04

## 背景

重构前，定时任务分为两类：
1. **内置函数任务**：硬编码在 `jobs.py` 中，执行特定 Python 函数（如 `WorldPipeline.run()`、`DailyReportAgent.run()`），由开发者在代码中定义，用户无法自行添加或修改。
2. **Chat 任务**：在 `config.yaml` 的 `scheduler_jobs` 字段配置 prompt，执行时调用 `ChatAgent.run(prompt)`。

这种分类造成了以下问题：
- 用户需要了解哪些任务是"内置"的，哪些是"可配置"的，认知负担高
- 添加新的定时任务需要修改 Python 代码，无法通过对话或 CLI 完成
- 内置任务和 Chat 任务的执行路径、日志记录、错误处理逻辑各自独立，维护成本高

## 决策

**取消"内置函数任务"概念，所有定时任务统一为 Chat 任务。**

- 所有任务均为 `ScheduledJob(id, display_name, cron, enabled, prompt, output_dir?)` 数据结构
- 存储在 `{data_dir}/memory/scheduled_jobs.yaml`，纯数据，无代码
- 统一通过 `_run_scheduled_job(job_id, prompt, output_dir?)` 执行，内部调用 `ChatAgent.run()`
- 原内置任务（晨报、日报、周报、季报、学习推送、世界新闻采集）转换为预置 prompt，首次启动写入 yaml

## 备选方案

### 方案一（被放弃）：保留内置任务，仅扩充 Chat 任务配置

保持两类任务并存，为 Chat 任务增加更多 CLI 管理命令。

放弃原因：根本矛盾未解决——内置任务仍需改代码才能新增，双轨制维护成本持续存在。

### 方案二（被放弃）：将内置任务包装为 ChatAgent system_prompt 注入

保留内置 Python 函数，但在调用前注入额外 system_prompt 使其外观与 Chat 任务一致。

放弃原因：本质上仍是两套执行路径，只是加了一层包装，不能解决任务可管理性问题。

## 结果

### 正面影响
- 用户可通过 `huaqi chat` 对话和 `huaqi scheduler` CLI 完成所有任务的 CRUD，无需改代码
- 执行路径、错误处理、执行日志统一，`_run_scheduled_job` 是唯一入口
- 任务定义纯数据化，yaml 文件人类可读，可直接编辑
- daemon 进程通过 mtime 轮询感知 yaml 变更并自动重载，无需重启

### 负面影响与缓解
- **LLM 可靠性**：原内置任务直接调用 Python 函数，100% 可靠；Chat 任务依赖 LLM 正确执行 prompt，存在概率性失败。缓解：`execution_log` 记录每次结果，`startup_recovery` 补跑失败任务。
- **output_dir 注入不可验证**：通过 prompt 前缀要求 LLM 将结果写入指定文件，但无法强制保证。这是已知限制（见 `docs/plans/2026-09-04-scheduler-deep-audit.md` Bug H），当前优先级下可接受。

## 相关文件

- `huaqi_src/scheduler/scheduled_job_store.py`
- `huaqi_src/scheduler/job_runner.py`
- `huaqi_src/scheduler/jobs.py`
- `docs/features/scheduler.md`
