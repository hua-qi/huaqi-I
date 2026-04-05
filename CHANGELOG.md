# Changelog

所有版本变更记录在此文件中，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [Unreleased]

### Added
- **WorldPipeline 独立采集流程**：新增 `huaqi_src/layers/data/world/pipeline.py`，封装 RSS 世界新闻抓取与存储为独立可调用流程，写入 `{data_dir}/world/YYYY-MM-DD.md`。
- **JobExecutionLog 调度器执行日志**：新增 `huaqi_src/scheduler/execution_log.py`，基于 SQLite `job_execution_log` 表记录每次任务执行的起止时间与状态，支持按 job_id + scheduled_at 查询。
- **MissedJobScanner 遗漏任务扫描器**：新增 `huaqi_src/scheduler/missed_job_scanner.py`，通过 APScheduler CronTrigger 枚举指定时间窗口内应触发的时间点，比对执行日志返回未成功执行的任务列表。
- **StartupJobRecovery 启动补跑**：新增 `huaqi_src/scheduler/startup_recovery.py`，CLI 启动时对比上次打开时间与当前时间，后台线程自动补跑遗漏任务，并通过 `scheduler_meta.json` 持久化 `cli_last_opened` 时间戳。
- **SchedulerJobConfig 配置开关**：`AppConfig` 新增 `scheduler_jobs: Dict[str, SchedulerJobConfig]` 字段，支持按 job_id 配置启用状态与自定义 cron 表达式。
- **WorldProvider lazy 补采**：`WorldProvider.get_context()` 在目标日期文件缺失时自动触发 `WorldPipeline.run()` 补采，失败则返回 `None`，不影响报告生成流程。
- **`huaqi world fetch` CLI 命令**：新增 `huaqi_src/cli/commands/world.py`，支持 `huaqi world fetch [--date YYYY-MM-DD]` 手动触发世界新闻采集。
- **`huaqi scheduler` CLI 命令组**：新增 `huaqi_src/cli/commands/scheduler.py`，提供 `list`、`enable <job_id>`、`disable <job_id>`、`set-cron <job_id> <cron>` 四个子命令，用于查看和管理定时任务配置。
- **jobs.py 新增 `world_fetch` 定时任务**：默认每日 07:00 触发 WorldPipeline 采集，cron 可通过 `scheduler_jobs` 配置覆盖。

### Changed
- `register_default_jobs()` 新增可选 `config: AppConfig` 参数，支持按配置跳过已禁用任务、使用自定义 cron。
- `ensure_initialized()` 末尾追加 `_run_startup_recovery()` 调用，CLI 每次启动时自动检测并后台补跑遗漏任务。
- **报告查看与生成系统**：新增统一的 `ReportManager` 用于处理所有报告的检索与实时生成。
- 新增 `huaqi report` 顶级 CLI 命令组，支持 `morning`, `daily`, `weekly` 子命令，可附加 `[date]` 及 `--force` 选项强制重新生成。
- 聊天内 `/report` 指令扩充，现支持 `/report [morning|daily|weekly|quarterly|insights] [date]` 实时获取或生成对应报告。

### Changed
- **三层架构完整迁移**：删除 `core/` 万能桶目录，所有业务模块按职责迁入 `layers/` 三层架构。
  - `core/event.py` + `core/db_storage.py` → `layers/data/events/`
  - `core/llm.py` → `layers/capabilities/llm/`
  - `core/profile_models.py` + `core/profile_manager.py` + `core/profile_narrative.py` → `layers/data/profile/`
  - `core/pattern_learning.py` → `layers/capabilities/pattern/`
  - `core/proactive_care.py` → `layers/capabilities/care/`
  - `core/flexible_store.py` → `layers/data/flexible/`
  - `core/ui_utils.py` → `cli/ui_utils.py`
  - `core/git_auto_commit.py` → `layers/data/git/`
- **配置管理统一**：`core/config_*.py` 系列整合为 `config/manager.py` + `config/paths.py` + `config/hot_reload.py`，新增 `get_config_manager()` 工厂函数。
- **测试目录规范化**：`tests/agent/` + `tests/cli/` + `tests/scheduler/` 整合入 `tests/unit/` 对应子目录，手动测试脚本移至 `scripts/`。
- **旧顶层目录清除**：`collectors/`、`world/`、`memory/`、`learning/`、`pipeline/`、`reports/`、`people/` 已在上一轮迁入 `layers/`，`core/` 在本轮彻底清空删除。

### Removed
- `huaqi_src/core/` 目录（万能桶，违反架构规范，全部按职责迁移）
- 根目录杂散脚本 `test_json.py`、`test_pty2.py`、`test_script.py`、`test_wrap.py`

---

### Added
- 学习助手新增 `mark_lesson_complete_tool`：标记当前章节为已完成，自动推进到下一章，已注册到 LangGraph ToolNode 和 `chat_nodes.py` bind_tools。
- `LessonOutline` 新增 `lesson_type` 字段（默认 `"quiz"`，可选 `"coding"` / `"project"`），支持 YAML 序列化，旧数据向后兼容。
- `CourseGenerator` 新增 `generate_outline_with_types()` 方法，通过关键词推断章节类型并返回 `List[tuple[str, str]]`。

### Changed
- `generate_feedback()` 新增 `passed: bool = None` 参数：`passed=True` 时末尾追加 `\n\n[PASS]`，`passed=False` 时追加 `\n\n[FAIL]`，不传则不变（向后兼容）。
- `start_lesson_tool` 创建新课程时改用 `generate_outline_with_types()`，同步写入每章 `lesson_type`。
- `CourseGenerator` 从 `start_lesson_tool` 函数内部导入改为 `learning_tools.py` 模块顶部导入，方便测试 Mock。

### Added
- 报告生成系统引入 DataProvider 注册表：新增抽象基类 `DataProvider`、全局注册表及 `build_context()` 统一入口，新增 7 个 Provider 实现（`WorldProvider`、`DiaryProvider`、`PeopleProvider`、`LearningProvider`、`GrowthProvider`、`EventsProvider`、`WeeklyReportsProvider`）。
- `WeeklyReportAgent` 和 `QuarterlyReportAgent` 新增 `LearningProvider` 和 `GrowthProvider` 数据来源（原版无此两项）。

### Changed
- `MorningBriefAgent`、`DailyReportAgent`、`WeeklyReportAgent`、`QuarterlyReportAgent` 的 `_build_context()` 方法重构为调用 `context_builder.build_context()`，原内嵌数据读取逻辑迁移至对应 Provider。

### Removed
- 移除微信采集所有对外入口：`huaqi collector sync-wechat` CLI 命令、`search_wechat_tool` Agent Tool、`wechat_sync` 调度器定时任务。
- 相关底层代码文件（`wechat_reader.py`、`wechat_state.py`、`wechat_writer.py`、`wechat_watcher.py`、`wechat_webhook.py`）保留但已封存，文件头加注声明：非作者本人声明不得重新添加任何入口。原因同前：微信 4.x macOS 版 SQLCipher 加密 + macOS SIP 保护，无合规读取路径。

### Added
- 重新实现微信聊天记录采集模块，新增 `wechat_reader.py`（`WeChatDBReader` + `WeChatMessage`）、`wechat_state.py`（增量同步状态持久化）、`wechat_writer.py`（Markdown 归档）、`wechat_watcher.py`（整合三者的 `WeChatWatcher`）。
- `pyproject.toml` 新增 `asyncio_mode = "auto"` 配置，支持 `pytest-asyncio` 异步测试。

### Changed
- **路径统一化重构**：将全项目中硬编码的数据子路径改为统一通过 `config_paths.py` 函数管理，所有路径现随用户配置的 `data_dir` 变化。新增以下 9 个路径函数：`get_diary_dir()`、`get_conversations_dir()`、`get_work_docs_dir()`、`get_cli_chats_dir()`、`get_wechat_dir()`、`get_inbox_work_docs_dir()`、`get_wechat_db_dir()`、`get_people_dir()`、`get_world_dir()`。
- 学习助手数据目录从 `{data_dir}/memory/learning/` 调整为 `{data_dir}/learning/`，与其他顶级目录（`people/`、`world/`）保持一致层级。
- `PeopleGraph`、`WorldNewsStorage`、`DailyReportAgent`、`MorningBriefAgent`、`WeeklyReportAgent`、`InboxProcessor`、`WeChatWriter` 均改为：传入 `data_dir` 时优先使用，未传时通过 `config_paths` 全局函数获取。
- `scheduler/jobs.py` 中 `_get_learning_store()` 改用 `get_learning_dir()`。
- `cli/__init__.py` 中 `MEMORY_DIR` 改用 `get_memory_dir()` 获取。
- `cli/commands/system.py` 两处 `ctx.DATA_DIR / "memory"` 改用 `get_memory_dir()`。
- `cli/inbox.py` 两处路径改用 `get_inbox_work_docs_dir()` / `get_work_docs_dir()`。
- `agent/nodes/chat_nodes.py` 两处 `memory/conversations` 改用 `get_conversations_dir()`。

### Fixed
- 修复 `tests/cli/test_study_cli.py::test_study_list_with_courses` 中测试数据写入旧路径导致的断言失败。

### Added
- 学习助手模块 `huaqi_src/learning/`：支持系统性技术学习（大纲生成 → 章节讲解 → 出题考察 → 进度持久化）。
- 新增 3 个 Agent 工具：`get_learning_progress_tool`、`get_course_outline_tool`、`start_lesson_tool`，已注册到 LangGraph ToolNode，用户可在对话中直接触发学习流程。
- 新增 `huaqi study` CLI 命令，支持查看课程列表（`--list`）、开始学习（`huaqi study <技术名>`）、重置进度（`--reset`）。
- 新增学习进度定时推送：`learning_daily_push` 每晚 21:00 自动生成进行中课程的复习题，通过 Scheduler 触发。
- 学习进度通过 YAML 文件持久化到 `{data_dir}/memory/learning/courses/<slug>/outline.yaml`，学习会话记录存入 `sessions/YYYYMMDD_<slug>.md`。

### Added
- 跨 Session 记忆召回（双轨制）：
  - 自动层：`retrieve_memories` 节点在向量库检索之外，额外扫描当天 `memory/conversations/` Markdown 文件，使用 2-gram 关键词宽松匹配，覆盖同一天内向量库尚未收录的对话。
  - 工具层：新增 `search_huaqi_chats_tool`，LLM 可按需深度检索全部历史 Huaqi 对话（向量库 + Markdown 全文）。
  - 注入优化：`generate_response` 的记忆注入限制每条 200 字、总量 1000 字，防止 token 超限。

### Removed
- 移除微信聊天记录采集功能：删除 `WeChatWatcher`、`WeChatDBReader`、`WeChatWriter`、`WeChatSyncState` 及全部相关代码。原因：微信 4.x macOS 版本改用 SQLCipher 加密存储，且 SIP 保护阻止了必要的进程签名操作，无法在不破坏系统安全策略的前提下读取本地数据库。
- 移除 `search_wechat_tool` Agent Tool。
- 移除 `huaqi collector sync-wechat` CLI 命令。
- 移除 `modules.wechat` 配置项及相关调度器定时任务 `wechat_sync`。

### Added
- Phase 3 监听采集：新增 `CLIChatWatcher`，监听用户配置的 CLI 工具对话目录（codeflicker Markdown / Claude JSON），解析并写入 `memory/cli_chats/YYYY-MM/<工具名>-<文件名>.md`。
- Agent Tools：新增 `search_cli_chats_tool`，允许 LangGraph Agent 在回答时检索 CLI 对话历史。
- CLI：新增 `huaqi collector` 子命令组（`status` / `sync-cli`），支持手动触发采集和查看模块开启状态。
- 新增 `docs/features/listeners.md` 监听采集功能文档。

### Added
- 新增 `huaqi resume <task_id> [response]` 命令，支持 LangGraph 工作流的中断恢复（人机协同）。
- 新增 `huaqi daemon` 命令（start/stop/status/list），支持后台定时任务管理。
- 新增 `huaqi pipeline review` 命令，支持内容流水线的人工审核机制。
- 新增 `huaqi personality review` 和 `huaqi personality update` 命令，支持人格画像自动更新与人工审核。
- 新增 `huaqi system hot-reload` 和 `huaqi system migrate` 命令，支持配置热更新与数据迁移。
- 引入 ChromaDB + BM25 的混合向量检索，大幅提升相关记忆片段的提取准确率。

### Changed
- 重构核心对话引擎，全面迁移至基于 `langgraph.graph.StateGraph` 的 Agent 架构。
- 优化 APScheduler 调度器集成，降级至稳定的 3.x 版本，并支持在 CLI 前后台安全运行。
- 重新组织和拆分各个模块代码至 `agent/`, `pipeline/`, `scheduler/`。

### Fixed
- 修复了新版 `langgraph-checkpoint-sqlite` 的 API 变更导致的连接断开与版本不匹配错误。
- 修复了前台运行 Daemon 时由于缺少事件循环导致的 `RuntimeError` 崩溃。

### Added
- 核心引擎：新增 `ConfigManager` 以支持默认关闭（Opt-in）的系统模块开关配置（网络代理、微信拦截等）。
- 核心引擎：新增带正则自动脱敏机制的统一 `Event` 数据结构。
- 核心引擎：新增基于 SQLite 的 `LocalDBStorage`，用于持久化存储微信和 CLI 的系统交互事件，数据文件自动落盘到系统统一定义的数据目录。
- Agent 模块：新增 `search_events_tool`，允许大模型在回答时通过 Tool Calling 自主检索本地 SQLite 中保存的交互事件历史。
- CLI：`huaqi config show` / `huaqi config set` 现支持查看和修改模块开关配置（如 `modules.network_proxy`, `modules.wechat`），并支持将内联值转换为 Boolean 类型落盘持久化。

### Changed
- CLI：修改了 `huaqi config set` 命令签名，现在支持在同一行直接传入目标值（例如 `huaqi config set modules.wechat true`），如果未传参则回退为 Prompt 询问。
- 核心存储：修复底层 `LocalDBStorage` 初始化路径，从硬编码的当前目录改为使用系统规范的 `~/.huaqi/events.db` 路径（遵循全局数据目录配置）。

### Fixed
- CLI：修复了执行 `huaqi config set <key> <value>` 时抛出的 `Got unexpected extra argument` Typer 报错问题。

### Fixed
- 修复 LangGraph Agent 模式下对话没有流式输出的问题：通过传递 `RunnableConfig` 并在底层节点明确使用 `astream` 遍历抛出流式事件
- 修复终端 UI 中用户输入被重复渲染的问题：在 prompt 返回后使用 ANSI 转义序列清屏而不关闭 `prompt_toolkit` 回显
- 修复 AI 回复内容颜色与 AI 名称颜色区分度不高的问题：改为 `bright_yellow`，且正确处理 Markdown 实时流式渲染
- 修复收到流式响应前没有 Loading 动画的问题：加入 `[dim]·  ·  ·[/dim]` 呼吸占位动画

### Added
- Agent 记忆检索：新增 `search_diary_tool` 并通过 `bind_tools` 绑定至 LangGraph LLM 节点，支持流式输出的同时自动路由工具调用，解决意图识别的“记忆断层”问题
- LangGraph Agent 模式成为默认对话入口（`huaqi` / `huaqi chat`）
- `ChatAgent` 类：流式输出（threading + Queue 桥接 async generator）、会话新建/恢复
- `AsyncSqliteSaver` checkpoint 持久化：会话上下文保存到 `{DATA_DIR}/checkpoints.db`，重启可恢复
- `huaqi chat -l` 列出历史会话，`-s <thread_id>` 恢复指定会话
- `analyze_user_understanding` 节点：情绪/能量/焦虑/动机维度分析
- `save_conversation` 节点：Markdown + Chroma 双写入（对话存档 + 向量索引）
- `memory_retriever` 激活 Embedding 向量检索（`bge-small-zh` + BM25 混合）
- 新增 `docs/features/langgraph-agent.md` LangGraph Agent 功能文档
- 新增 `docs/features/conversation-context.md` 对话上下文机制文档
- 新增 `docs/design/adr/ADR-004-langgraph-default-mode.md` 架构决策记录
- 新增 `docs/design/adr/ADR-003-memory-retrieval-strategy.md` 记忆检索策略决策
- 新增 `docs/design/memory-retrieval-strategy.md` 记忆检索方案分析文档
- 新增 `BubbleLayout` 类（`huaqi_src/core/ui_utils.py`）：无边框气泡对话布局，支持 60% 宽度居中、左右分列显示

### Changed
- `generate_response` 节点改用 `ChatOpenAI(streaming=True)` + `async def`，支持 `astream_events` 事件追踪
- `huaqi`（无子命令）从传统模式改为走 LangGraph 模式
- `pyproject.toml` 新增 `langgraph-checkpoint-sqlite` 和 `aiosqlite>=0.17.0,<0.20` 依赖
- CLI 对话界面全面重设计：去除所有 Panel 边框，采用无边框气泡布局
- AI 回复：`🌸 HH:MM` 前缀 + Markdown 正文，左对齐，右边界锁定在内容列
- 用户消息：右对齐纯文本，使用 `rich.cells.cell_len` 正确处理中文双宽字符对齐
- 启动流程：关怀消息延迟至第一轮回复后展示，周报静默后台生成，分析提示完全移除
- 输入提示符动态显示对话轮数：`🌸 huaqi [N] >`
- 移除每轮对话分隔线

### Changed
- CLI 命令统一简化：所有子命令组均收敛为 `show` + `set` 两个标准子命令
- `config list` 重命名为 `config show`
- `profile` 删除 `refresh`、`forget` 子命令，保留 `show`、`set`
- `personality` 删除 `update`、`review` 子命令，新增 `set`（提示不支持手动设置）
- `pipeline`、`system` 各新增 `show` 子命令展示模块状态，操作类子命令保持不变
- CLI 全局 Options 简化：移除 `--data-dir`、`--install-completion`、`--show-completion`
- 首次运行未设置数据目录时自动触发引导向导（原 `--data-dir` 功能合并到 `config set data_dir`）
- `huaqi --help` 命令列表按"配置管理"和"操作工具"两组展示
- 代码组织重构：`cli.py` 从 2278 行拆分为 `huaqi_src/cli/` 包（`ui.py` / `context.py` / `chat.py` / `commands/`）
- 代码组织重构：`user_profile.py` 从 1097 行拆分为 `profile_models.py` / `profile_manager.py` / `profile_narrative.py` / `profile_extractor.py`
- `user_profile.py` 保留为向后兼容的 re-export 入口，所有现有导入无需修改
- 新增 `huaqi_src/core/__init__.py`，统一导出 core 层公开 API
- 清理 5 个空目录（`orchestration/`、`security/`、`skills/`、`memory/layers/`、`memory/sync/`）
- 迁移根目录散落的测试脚本到 `tests/unit/`

### Added
- 新增 `docs/guides/dev/code-standards.md` 代码及文件组织规范（供 agent 生成代码参考）

## [0.2.0] - 2026-03-28

### Added
- 模式学习与主动关怀系统（Phase 10）
- 核心分析引擎与用户画像系统（Phase 9）
- 配置热重载与数据迁移（Phase 8）
- 人机协同中断恢复机制（Phase 6）

### Changed
- 将 `huaqi/` 重命名为 `huaqi_src/` 以区分运行时数据目录

## [0.1.0] - 2026-03-25

### Added
- 基础对话系统（LangGraph Agent）
- 记忆系统（日记 + 对话历史）
- 技能追踪与目标管理
- APScheduler 定时任务
- 内容流水线（X/RSS → 小红书）
- Git 数据同步
