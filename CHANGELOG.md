# Changelog

所有版本变更记录在此文件中，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [Unreleased]

### Changed
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
