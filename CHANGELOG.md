# Changelog

所有版本变更记录在此文件中，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [Unreleased]

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
- 新增 `spec/decisions/ADR-004-langgraph-default-mode.md` 架构决策记录
- 新增 `spec/decisions/ADR-003-memory-retrieval-strategy.md` 记忆检索策略决策
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
- 新增 `docs/guides/code-organization.md` 代码及文件组织规范（供 agent 生成代码参考）

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
