# Huaqi 代码与目录规范文档

> **文档作用**: 本文档指导开发时的代码组织结构、层级划分与开发规范。
> 本文档是 2026-01-04 架构升级的配套规范，所有后续开发必须遵守。

---

## 一、目录结构规范

### 1.1 标准目录结构

```
huaqi_src/
├── agent/                    # LangGraph Agent 层
│   ├── state.py              # 全局 AgentState 定义
│   ├── graph/                # 各 workflow 状态图
│   └── nodes/                # 各 workflow 节点实现
│
├── cli/                      # CLI 层（Typer）
│   ├── __init__.py           # app 挂载点
│   ├── chat.py               # 对话主循环
│   ├── context.py            # 全局组件缓存
│   ├── ui.py                 # UI 组件
│   └── commands/             # 子命令（每个命令一个文件）
│
├── config/                   # 配置管理
│   ├── __init__.py
│   ├── models.py             # 配置数据模型（Pydantic）
│   ├── manager.py            # 配置加载/保存/热重载
│   └── paths.py              # 数据目录路径管理
│
├── layers/                   # 三层架构（核心业务）
│   │
│   ├── data/                 # ── 数据层：收、存、不丢 ──
│   │   ├── raw_signal/       # 统一摄取（所有输入的入口）
│   │   │   ├── __init__.py
│   │   │   ├── models.py     # RAW_SIGNAL 数据模型
│   │   │   ├── store.py      # SQLite 持久化
│   │   │   ├── pipeline.py   # 信号提炼触发管道
│   │   │   └── converters/   # 各数据源转换器
│   │   │       ├── base.py
│   │   │       ├── diary.py
│   │   │       ├── chat.py
│   │   │       └── wechat.py
│   │   ├── memory/           # 向量检索
│   │   │   ├── vector/       # ChromaDB 封装
│   │   │   └── search/       # BM25 + 向量混合检索
│   │   └── collectors/       # 外部数据采集（MCP 适配器）
│   │
│   ├── growth/               # ── 成长层：理解、提炼、更新 ──
│   │   └── telos/            # TELOS 知识图谱
│   │       ├── __init__.py
│   │       ├── models.py     # TELOS 维度数据模型
│   │       ├── manager.py    # 版本化读写
│   │       ├── engine.py     # RAW_SIGNAL → TELOS 提炼引擎
│   │       ├── growth_events.py  # 成长事件
│   │       ├── meta.py       # META 维度（提炼偏好校正）
│   │       └── dimensions/   # 各维度扩展逻辑（可选）
│   │
│   └── capabilities/         # ── 能力层：帮用户干活 ──
│       ├── __init__.py
│       ├── reports/          # 定时报告（晨/日/周/月/年报）
│       │   ├── providers/    # 各数据提供者
│       │   ├── daily.py
│       │   ├── weekly.py
│       │   ├── monthly.py
│       │   ├── annual.py
│       │   └── morning.py
│       ├── learning/         # 学习追踪
│       │   ├── models.py
│       │   ├── tracker.py
│       │   └── scheduler.py
│       └── pipeline/         # 内容流水线
│           ├── models.py
│           ├── core.py
│           ├── sources/
│           ├── processors/
│           └── platforms/
│
├── scheduler/                # 定时任务（驱动三层运转）
│   ├── manager.py
│   ├── handlers.py
│   └── jobs.py
│
└── integrations/             # 外部集成（Webhook 等）
```

### 1.2 目录命名规则

| 规则 | 正确 | 错误 |
|---|---|---|
| 使用名词，不使用动词 | `telos/` | `analyze/` |
| 小写下划线 | `raw_signal/` | `RawSignal/` |
| 名称即职责，见名知意 | `collectors/` | `utils/` |
| 禁止万能桶目录 | — | `core/`、`common/`、`helpers/` |

### 1.3 禁止的目录模式

```
❌ core/          # 职责不明的万能桶
❌ utils/         # 无边界的工具集合
❌ helpers/       # 同上
❌ common/        # 同上
❌ misc/          # 同上
```

如果发现需要 `utils/`，说明该功能应该归属某个具体模块。

---

## 二、文件命名规范

### 2.1 标准文件角色

每个模块内，文件按以下角色命名：

| 文件名 | 职责 | 示例 |
|---|---|---|
| `models.py` | Pydantic 数据模型定义 | `telos/models.py` |
| `manager.py` | 有状态的业务管理器 | `telos/manager.py` |
| `store.py` | 纯数据持久化层 | `raw_signal/store.py` |
| `engine.py` | 计算/分析/提炼逻辑 | `telos/engine.py` |
| `base.py` | 抽象基类 | `converters/base.py` |
| `__init__.py` | 模块公开接口导出 | 所有模块 |

### 2.2 文件命名禁令

```
❌ diary_simple.py       # _simple 是过渡期临时命名，不允许保留
❌ profile_v2.py         # _v2 / _new / _old 禁止出现在正式代码
❌ adaptive_understanding.py  # 动词短语，职责模糊
❌ deep_analysis.py      # 形容词修饰，边界不清
❌ user_profile.py       # 重复导出文件（re-export 文件不允许存在）
```

### 2.3 正确命名示例

```
✅ telos/engine.py       # 模块名/角色名，清晰
✅ raw_signal/store.py   # 清晰的持久化职责
✅ config/manager.py     # 清晰的管理职责
```

---

## 三、代码规范

### 3.1 模块职责原则

**一个目录 = 一个业务概念，不允许跨越**

```python
# ✅ 正确：telos 模块只处理 TELOS 相关逻辑
# telos/manager.py
class TelosManager:
    def read_dimension(self, dimension: str) -> TelosDimension: ...
    def write_dimension(self, dimension: TelosDimension) -> None: ...

# ❌ 错误：在 telos 里处理 raw_signal 的逻辑
class TelosManager:
    def process_raw_signal(self, signal: dict) -> None: ...  # 不属于这里
```

### 3.2 依赖方向规则

依赖只能单向向下，禁止反向依赖：

```
cli
 ↓
agent
 ↓
layers/growth/telos  ←→  layers/data/raw_signal
 ↓
layers/data/memory / config
 ↓
（外部库）

layers/capabilities/ 可以依赖上面所有层，但不被任何层依赖
scheduler/ 可以驱动三层，但不包含业务逻辑
```

```python
# ✅ 正确：agent 依赖 telos
from huaqi_src.layers.growth.telos import TelosManager

# ✅ 正确：capabilities 依赖 telos 和 raw_signal
from huaqi_src.layers.growth.telos import TelosManager
from huaqi_src.layers.data.raw_signal import RawSignalStore

# ❌ 错误：telos 依赖 agent（反向）
from huaqi_src.agent import AgentState  # 禁止

# ❌ 错误：data 层依赖 growth 层（反向）
from huaqi_src.layers.growth.telos import TelosManager  # 禁止出现在 data/ 内
```

### 3.3 __init__.py 规范

`__init__.py` 只做公开接口导出，不写业务逻辑：

```python
# ✅ 正确：telos/__init__.py
from .models import TelosDimension, TelosSnapshot
from .manager import TelosManager
from .engine import TelosEngine

__all__ = ["TelosDimension", "TelosSnapshot", "TelosManager", "TelosEngine"]

# ❌ 错误：在 __init__.py 里写业务逻辑
def update_telos(data):  # 不允许
    ...
```

外部代码只通过模块名 import，不穿透到内部文件：

```python
# ✅ 正确
from huaqi_src.layers.growth.telos import TelosManager

# ❌ 错误：穿透内部文件
from huaqi_src.layers.growth.telos.manager import TelosManager
```

### 3.4 数据模型规范

所有业务数据结构必须使用 Pydantic 模型，禁止裸 dict 传递：

```python
# ✅ 正确
class RawSignal(BaseModel):
    id: str
    user_id: str
    source_type: SourceType
    timestamp: datetime
    content: str
    processed: bool = False

def process_signal(signal: RawSignal) -> None: ...

# ❌ 错误：裸 dict
def process_signal(signal: dict) -> None: ...
```

### 3.5 Docstring 规范

所有公开类和函数必须有 docstring，说明**做什么**，不说**怎么做**：

```python
# ✅ 正确
class TelosEngine:
    """将 RAW_SIGNAL 提炼成 TELOS 维度更新的引擎。"""

    def analyze(self, signal: RawSignal) -> list[DimensionUpdate]:
        """分析单条信号，返回受影响的 TELOS 维度更新列表。"""

# ❌ 错误：说怎么做
class TelosEngine:
    """通过调用 LLM API 然后解析 JSON 响应来更新 TELOS。"""  # 实现细节不该在这里
```

### 3.6 错误处理规范

```python
# ✅ 正确：定义领域专属异常
class TelosUpdateError(Exception):
    """TELOS 更新失败时抛出。"""

# ✅ 正确：明确捕获，不吞掉异常
try:
    manager.write_dimension(dimension)
except TelosUpdateError as e:
    logger.error("telos_update_failed", dimension=dimension.name, error=str(e))
    raise

# ❌ 错误：裸 except 吞掉所有异常
try:
    manager.write_dimension(dimension)
except:
    pass
```

### 3.7 单例/全局状态规范

使用工厂函数管理单例，不使用模块级全局变量：

```python
# ✅ 正确
_telos_manager: TelosManager | None = None

def get_telos_manager() -> TelosManager:
    """获取全局 TelosManager 单例。"""
    global _telos_manager
    if _telos_manager is None:
        raise RuntimeError("TelosManager 未初始化，请先调用 init_telos_manager()")
    return _telos_manager

def init_telos_manager(data_dir: Path) -> TelosManager:
    """初始化全局 TelosManager。"""
    global _telos_manager
    _telos_manager = TelosManager(data_dir)
    return _telos_manager

# ❌ 错误：模块级直接初始化
telos_manager = TelosManager(Path("~/.huaqi"))  # 导入时就执行，不可控
```

---

## 四、改造执行规范

### 4.1 改造三原则

1. **新建优先于修改**：先建新模块，再迁移，最后删旧代码
2. **删除必须彻底**：迁移完成后旧文件必须删除，不留「备用」
3. **不允许过渡期代码进入主分支**：`_simple`、`_v2`、`TODO: 迁移` 等标记不允许合并

### 4.2 改造检查清单

每次改造完成后，验证以下内容：

```
□ 新模块有完整的 __init__.py 导出
□ 新模块所有公开类/函数有 docstring
□ 旧文件已删除（不是注释掉）
□ 没有任何文件引用已删除的模块
□ 依赖方向符合单向规则
□ 没有裸 dict 传递业务数据
□ 没有 _simple / _v2 等临时命名
□ ruff 检查通过（无 lint 错误）
□ mypy 检查通过（无类型错误）
```

### 4.3 本次改造的文件清理列表

架构升级完成后，以下文件必须删除：

**core/ 下需删除（迁移到 telos/ 后删除）：**
```
core/profile_models.py
core/profile_manager.py
core/profile_narrative.py
core/profile_extractor.py
core/user_profile.py          # re-export 文件，直接删
core/personality_simple.py
core/personality_updater.py
core/adaptive_understanding.py
core/pattern_learning.py
core/proactive_care.py
core/proactive_exploration.py
core/analysis_engine.py
core/deep_analysis.py
core/dimension_manager.py
core/flexible_store.py
core/schema.py
```

**core/ 下需合并（迁移到 config/ 后删除）：**
```
core/config_paths.py    → config/paths.py
core/config_simple.py   → config/manager.py
core/config_hot_reload.py → config/manager.py
core/config_manager.py  → config/manager.py
```

**reports/、learning/、pipeline/ 需迁移（迁移到 layers/capabilities/ 后删除）：**
```
reports/    → layers/capabilities/reports/
learning/   → layers/capabilities/learning/
pipeline/   → layers/capabilities/pipeline/
```

**raw_signal/、memory/、collectors/ 需迁移（迁移到 layers/data/ 后删除）：**
```
raw_signal/ → layers/data/raw_signal/
memory/     → layers/data/memory/
collectors/ → layers/data/collectors/
```

**people/ 需迁移（迁移到 layers/growth/telos/dimensions/ 后删除）：**
```
people/models.py        → layers/growth/telos/dimensions/people.py
people/graph.py         → layers/growth/telos/dimensions/people.py
people/extractor.py     → layers/growth/telos/dimensions/people.py
```

---

## 五、架构约束速查

```
数据流向（单向）
  外部数据 → layers/data/raw_signal → layers/growth/telos → agent → cli → 用户

模块依赖（单向向下）
  cli → agent → layers/growth + layers/data → config

能力层特殊规则
  layers/capabilities/ 可依赖三层所有模块，但不被任何层依赖
  scheduler/ 驱动三层运转，但不包含业务逻辑

存储职责分工
  SQLite    → RAW_SIGNAL 结构化存储（layers/data/raw_signal/）
  ChromaDB  → RAW_SIGNAL 向量化（layers/data/memory/）
  Markdown  → TELOS 维度（layers/growth/telos/，人类可读，Git 管理）
  YAML      → 配置文件（config/）

新增功能的归属判断
  这是「收数据」？          → layers/data/raw_signal/converters/
  这是「理解用户」？        → layers/growth/telos/
  这是「帮用户干活」？      → layers/capabilities/ 下新建子目录
  这是「对外连接」？        → layers/data/collectors/ 或 integrations/
```

---

**文档版本**：v1.2
**创建时间**：2026-01-04
**更新说明**：三层架构统一归入 layers/ 目录，data/growth/capabilities 层级一目了然
**对应架构**：个人成长系统完整设计文档 v1.0
