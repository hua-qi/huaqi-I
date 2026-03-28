# ADR-002: 代码及文件组织规范化重构

**状态**: 已采纳
**日期**: 2026-03-29

## 背景

项目经过 Phase 1-10 的迭代后，代码组织出现了以下问题：

- `cli.py` 积累到 2278 行，命令、UI、对话逻辑、业务逻辑全部耦合，无法独立测试
- `huaqi_src/core/user_profile.py` 积累到 1097 行，包含 5 个不同职责的类（数据模型、持久化管理、LLM 叙事生成、后台提取）
- `core/` 模块无 `__init__.py`，边界不清晰，外部调用需要了解内部文件结构
- 存在多个空目录（`orchestration/`、`security/`、`skills/` 等），造成误解
- 测试文件散落在根目录，不符合 `pyproject.toml` 中 `testpaths = ["tests"]` 的配置

这些问题导致新功能难以定位放置位置，agent 生成代码时容易放错模块或重复创建文件。

## 决策

### 1. 建立代码组织规范文档

新增 `docs/guides/code-organization.md`，明确：
- 目录结构总览与各模块职责边界
- 文件命名规范（禁止 `new_`/`v2_`/`final_` 修饰词）
- 代码文件内部结构顺序（标准库 → 第三方 → 本地；常量 → 模型 → 类 → 单例）
- 命名约定、类型注解、docstring 格式、异常处理、单例模式
- `__init__.py` 规范与测试目录组织

### 2. 清理空目录

删除 `orchestration/`、`security/`、`skills/`、`memory/layers/`、`memory/sync/`，遵循"有实际需求时再创建"的原则。

### 3. 整合散落测试

将根目录 `test_*.py` 迁移至 `tests/unit/`，与 `pyproject.toml` 配置保持一致。

### 4. 为 `core/` 新增 `__init__.py`

统一导出全部公开 API，消除调用方对内部文件结构的依赖。

### 5. 拆分 `user_profile.py`

按职责拆分为 4 个独立文件：

| 文件 | 职责 |
|------|------|
| `profile_models.py` | 数据模型（UserIdentity/Preferences/Background/Profile） |
| `profile_manager.py` | 持久化存储与字段更新 |
| `profile_narrative.py` | LLM 叙事性画像生成与缓存 |
| `profile_extractor.py` | 启动时后台数据提取（带重试） |

原 `user_profile.py` 改为纯 re-export，所有现有导入无需修改。

### 6. 拆分 `cli.py`

将 2278 行单文件拆分为 `huaqi_src/cli/` 包：

| 文件 | 职责 |
|------|------|
| `ui.py` | 命令补全器、输入框、清屏等 UI 组件 |
| `context.py` | 全局组件缓存、`ensure_initialized` |
| `chat.py` | 对话主循环与所有斜杠命令处理 |
| `commands/config.py` | `config` 子命令 |
| `commands/profile.py` | `profile` 子命令 |
| `commands/pipeline.py` | `pipeline` 子命令 |
| `commands/personality.py` | `personality` 子命令 |
| `commands/system.py` | `system` + `daemon` 子命令 |

`cli.py` 缩减为 18 行入口，通过 `from huaqi_src.cli import app` 挂载。

## 备选方案

**方案 A：保持现状，仅添加注释**
不采纳。注释无法解决模块边界不清、文件过大难以单测的根本问题。

**方案 B：按依赖层级重组 core/ 子目录**
（将 core/ 拆为 foundation/storage/analysis/intelligence 子包）
当前暂不采纳。收益不如拆分 cli.py 和 user_profile.py 明显，且风险更高（大量 import 路径变更）。待未来有明确需求时再评估。

**方案 C：引入依赖注入框架**
不采纳。项目规模下全局单例模式已足够，引入 DI 框架增加认知负担。

## 结果

- `cli.py` 从 2278 行降至 18 行，各命令模块最大不超过 250 行
- `user_profile.py` 从 1097 行降至 54 行（re-export），单职责文件最大 385 行
- 所有现有导入路径无需修改（向后兼容）
- `python3 cli.py --help` 及所有子命令验证通过
- 技术债务清零，后续新功能有明确的归属模块
