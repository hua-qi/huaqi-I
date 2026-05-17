# Spec: telos-distillation-scheduling

> Spec 是功能的顶层设计，只描述 WHAT 和 WHY，不描述 HOW。

## 1. 要解决的问题

TELOS 引擎的代码和蒸馏管道（`DistillationPipeline` → `TelosEngine`）已完整实现，但蒸馏的**自动触发机制**在本地 daemon 移除后断链。聊天对话、日记、工作日志会被采集为 `RawSignal` 存入数据库，但永远以 `processed=0` 的状态沉睡——没有人来定期捞取它们并送入蒸馏管道。同时，`pytest-asyncio` 未列入 dev 依赖，导致 15 个异步测试报假失败。

## 2. 功能范围

**包含：**
- 将 `pytest-asyncio` 加入 dev 依赖，修复配置了 `asyncio_mode = "auto"` 但缺依赖的 bug
- 创建一个定期执行的 TELOS 信号蒸馏任务，捞取 `processed=0` 的 `RawSignal` 并送入 `DistillationPipeline.process()`
- 支持在 GitHub Actions 环境中运行（不依赖本地 daemon）
- 蒸馏完成后将信号标记为 `processed=1`

**不包含：**
- 世界新闻、学习推送等其他内容触发 telos 蒸馏（它们不是用户个人信号，不反映认知变化）
- 新增信号采集渠道（聊天/日记/工作文档的采集代码已存在，不在此范围内）
- 改变 `DistillationPipeline` 或 `TelosEngine` 的核心逻辑
- People 子系统改动
- 冷启动问卷改动

## 3. 触发 telos 蒸馏的信号

| 信号源 | SourceType | 应触发蒸馏？ | 原因 |
|--------|-----------|:---:|------|
| 聊天对话 | `AI_CHAT` | 是 | 反映用户思考、情绪、目标变化 |
| 日记 | `JOURNAL` | 是 | 用户自我反思的直接表达 |
| 工作文档/日志 | `WORK_DOC` | 是 | 反映工作方式、挑战、策略 |
| 微信消息 | `WECHAT` | 是（如有采集） | 社交互动中的个人表达 |
| 世界新闻 | — | **否** | 外部信息消费，不反映用户认知 |
| 学习推送 | — | **否** | AI 生成的产出内容，不反映用户认知 |

蒸馏任务不对信号源类型做区分——只要 `processed=0` 就捞取。信号源类型的区分由采集阶段负责（只采集个人信号），蒸馏阶段无需重复判断。

## 4. 验收标准

- [ ] **AC-1**: `pytest-asyncio` 已加入 `pyproject.toml` 的 `[project.optional-dependencies] dev` 列表 → `test_dep_asyncio_in_dev`
- [ ] **AC-2**: 安装 dev 依赖后，`pytest tests/unit/layers/data/ tests/unit/layers/growth/ -v` 不再出现 "async def functions are not natively supported" 错误 → `test_all_async_tests_pass`
- [ ] **AC-3**: 存在一个可被 GitHub Actions 调用的蒸馏入口（CLI 命令或 Python 脚本），接受 `--limit` 参数 → `test_distillation_entry_exists`
- [ ] **AC-4**: 调用蒸馏入口时，会查询 `processed=0` 的信号并逐条送入 `DistillationPipeline.process()` → `test_distillation_processes_unprocessed`
- [ ] **AC-5**: 无未处理信号时，蒸馏入口正常退出（返回 `processed: 0`，不报错）→ `test_distillation_no_unprocessed`
- [ ] **AC-6**: 单条信号蒸馏失败时，不影响其余信号的处理 → `test_distillation_error_isolation`
- [ ] **AC-7**: 蒸馏完成后信号被标记为 `processed=1` → `test_signal_marked_processed_after_distillation`
- [ ] **AC-8**: 新增的冒烟测试加入 `tests/smoke_test.py` 的 `TestTelosDistillationScheduling` 类

## 5. 依赖

- `huaqi_src/layers/data/raw_signal/pipeline.py` — `DistillationPipeline`（已存在）
- `huaqi_src/layers/growth/telos/engine.py` — `TelosEngine`（已存在）
- `huaqi_src/layers/data/raw_signal/store.py` — `RawSignalStore`（已存在）
- `huaqi_src/scheduler/job_runner.py` — `_run_scheduled_job`（已存在，参考模式）
- `huaqi_src/config/paths.py` — 数据目录路径函数（已存在）

## 6. 风险与假设

- **假设**：聊天对话在会话结束时被保存为 `RawSignal`（代码中 `cli/chat.py:861` 仅在 session 结束时调用 `save_conversation`，非逐条保存）
- **假设**：GitHub Actions 环境可以访问 `RawSignalStore` 的 SQLite 数据库和 TELOS 的 markdown 文件（数据目录在 huaqi 数据 repo 中）
- **风险**：蒸馏调用 LLM，会增加 API 费用。需设置合理的 `--limit` 控制每次处理量
