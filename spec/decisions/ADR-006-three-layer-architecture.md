# ADR-006: 三层架构完整迁移，删除 core/ 万能桶

**状态**: 已采纳
**日期**: 2026-02-04

## 背景

ADR-002 确立了代码组织规范，但当时选择了"备选方案 B 暂不采纳"——即未拆分 `core/` 目录。随着后续迭代，`core/` 持续膨胀，最终积累了 12 个不同职责的模块（约 3000 行），成为严格意义上的万能桶：

- LLM 抽象（`llm.py`）
- 用户画像（`profile_*.py` 3 个文件）
- 配置管理（`config_*.py` 3 个文件）
- 事件存储（`event.py`、`db_storage.py`）
- 分析引擎（`flexible_store.py`、`pattern_learning.py`）
- 主动关怀（`proactive_care.py`）
- UI 工具（`ui_utils.py`）
- Git 工具（`git_auto_commit.py`）

与此同时，旧顶层目录（`collectors/`、`world/`、`memory/`、`learning/`、`pipeline/`、`reports/`、`people/`）已在上一轮迁入 `layers/`，但 `core/` 作为依赖中枢仍大量被外部引用，形成"引力坑"效应——新代码倾向于继续放入 `core/`。

## 决策

### 1. 彻底删除 `core/` 目录

不保留任何 `core/` 中的文件，按职责逐一迁入 `layers/` 三层架构或 `config/`、`cli/`。

### 2. 迁移映射

| 原路径 | 新路径 | 所属层 |
|--------|--------|--------|
| `core/event.py` | `layers/data/events/models.py` | data |
| `core/db_storage.py` | `layers/data/events/store.py` | data |
| `core/llm.py` | `layers/capabilities/llm/manager.py` | capabilities |
| `core/profile_models.py` | `layers/data/profile/models.py` | data |
| `core/profile_manager.py` | `layers/data/profile/manager.py` | data |
| `core/profile_narrative.py` | `layers/data/profile/narrative.py` | data |
| `core/pattern_learning.py` | `layers/capabilities/pattern/engine.py` | capabilities |
| `core/proactive_care.py` | `layers/capabilities/care/engine.py` | capabilities |
| `core/flexible_store.py` | `layers/data/flexible/store.py` | data |
| `core/ui_utils.py` | `cli/ui_utils.py` | cli（非业务层） |
| `core/git_auto_commit.py` | `layers/data/git/auto_commit.py` | data |
| `core/config_*.py` (3个) | `config/manager.py` + `config/paths.py` + `config/hot_reload.py` | config（独立层） |

### 3. 统一配置管理

将分散在 `core/config_simple.py`、`core/config_manager.py`、`core/config_paths.py`、`core/config_hot_reload.py` 的配置逻辑合并为 `config/` 包，新增 `get_config_manager()` 无参工厂函数，消除"调用方需要传 `data_dir` 才能构造 `ConfigManager`"的不便。

### 4. 测试目录规范化

- `tests/agent/`、`tests/cli/`、`tests/scheduler/` 合并入 `tests/unit/` 各对应子目录
- 手动集成测试脚本（`test_llm_connection.py`、`test_*.py`）移至 `scripts/`，不参与 pytest

## 备选方案

**方案 A：保持 core/ 存在，仅添加边界注释**
不采纳。注释无法防止新代码持续堆入。

**方案 B：将 core/ 拆为多个子包（如 `core/infra/`、`core/domain/`）**
不采纳。只是挪动层级，不解决"万能桶"根本问题；且与已有 `layers/` 三层体系存在概念重叠。

**方案 C：分批迁移，先重命名 core/ 为 legacy/**
不采纳。`legacy/` 同样是万能桶，只是改了个名字，长期必然被忽略。

## 结果

- `core/` 目录已彻底删除（0 文件残留）
- 全项目无 `from huaqi_src.core.` 引用
- 无禁止目录（`core/`、`utils/`、`helpers/`、`common/`）
- 402 个测试通过，ruff 零错误
- 新功能归属模块清晰：数据类 → `layers/data/`，能力类 → `layers/capabilities/`，成长类 → `layers/growth/`

## 依赖方向规范（本次迁移强化）

```
cli/agent  →  layers/capabilities  →  layers/data  →  config/
                    ↓
             layers/growth
                    ↓
             layers/data
```

禁止：
- `layers/data/` 引用 `layers/capabilities/` 或 `layers/growth/`
- `layers/` 任意子层引用 `cli/` 或 `agent/`
- 跨层 re-export（禁止在 `__init__.py` 以外对外暴露内部模块路径）
