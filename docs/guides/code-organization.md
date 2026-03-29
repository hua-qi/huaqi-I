# 代码及文件组织规范

本规范供 agent 和开发者在新建文件、编写代码、重构模块时参考，确保项目代码始终保持一致、可维护的组织形式。

---

## 零、两个目录的区分（重要）

Huaqi 运行时涉及两个**完全不同**的目录，开发和调试时必须区分：

| 目录类型 | 内容 | 典型路径示例 |
|---------|------|------------|
| **源码目录** | git 克隆的代码仓库，包含 `huaqi_src/`、`cli.py`、`docs/` 等 | `~/workspace/huaqi-growing/` |
| **用户数据目录** | 运行时产生的用户数据，由 `--data-dir` 或 `HUAQI_DATA_DIR` 指定 | `~/workspace/huaqi/`、`~/.huaqi/` 等 |

**两者完全独立，不存在包含关系。** 用户数据目录的路径由用户自定义，可能与源码目录同名前缀（如都在 `~/workspace/` 下），但它们是两个平级的独立目录。

常见误区：
- `~/workspace/huaqi/` 是用户数据目录，**不是**源码仓库
- `~/workspace/huaqi-growing/` 才是源码仓库
- 用 VSCode 打开用户数据目录的父目录时，`huaqi/memory/` 下的文件会显示为 Untracked——这是正常现象，因为 `memory/` 有自己独立的 git 仓库

---

## 一、目录结构总览

```
huaqi-growing/
├── cli.py                        # CLI 入口（Typer app 挂载点）
├── pyproject.toml                # 项目配置、依赖、工具链配置
├── requirements.txt              # 依赖锁定
│
├── huaqi_src/                    # 核心源码包
│   ├── __init__.py               # 版本号、作者声明
│   ├── agent/                    # LangGraph Agent 层（对话流、意图路由）
│   │   ├── __init__.py           # 公开导出
│   │   ├── state.py              # 全局 State 定义（TypedDict）
│   │   ├── graph/                # 图结构定义
│   │   └── nodes/                # 各 workflow 节点
│   ├── core/                     # 业务逻辑层（配置、分析、用户模型等）
│   │   └── *.py                  # 平铺结构，每文件一个职责域
│   ├── memory/                   # 记忆存储层（向量、文本、混合检索）
│   │   ├── search/               # 检索算法
│   │   ├── storage/              # 持久化存储
│   │   └── vector/               # 向量数据库封装
│   ├── pipeline/                 # 内容流水线（采集 → 处理 → 发布）
│   │   ├── __init__.py
│   │   ├── models.py             # 数据模型（dataclass/Enum）
│   │   ├── core.py               # 流水线主逻辑
│   │   ├── sources/              # 内容源（RSS、X 等）
│   │   ├── processors/           # 处理器（摘要、翻译等）
│   │   └── platforms/            # 发布平台（小红书等）
│   └── scheduler/                # 定时任务层（APScheduler 封装）
│       ├── __init__.py
│       ├── manager.py            # 调度器管理
│       ├── handlers.py           # 任务处理器
│       └── pipeline_job.py       # 流水线定时任务
│
├── docs/                         # 文档（参见 DOC_GUIDELINES.md）
├── spec/                         # 规范与决策记录
├── templates/                    # 用户数据模板（memory、personality、skills）
├── tests/                        # 测试（参见第七节）
└── scripts/                      # 运维脚本（迁移、初始化等）
```

---

## 二、模块职责划分

每个顶级模块有明确边界，不得越界调用：

| 模块 | 职责 | 可依赖 | 不可依赖 |
|------|------|--------|---------|
| `agent/` | 对话流程、意图识别、LangGraph 图 | `core/`、`memory/` | `pipeline/`、`scheduler/` |
| `core/` | 配置管理、用户模型、分析引擎、LLM 调用 | 仅标准库和第三方库 | 其他 `huaqi_src` 子模块 |
| `memory/` | 记忆读写、向量检索、文本检索 | `core/`（仅配置路径） | `agent/`、`pipeline/` |
| `pipeline/` | 内容采集、处理、发布 | `core/`（仅 LLM、配置） | `agent/`、`memory/`、`scheduler/` |
| `scheduler/` | 定时任务调度 | `pipeline/`、`core/`（仅配置） | `agent/`、`memory/` |

**核心原则：依赖方向只能向下（agent → core，memory → core），不能反向，不能横向跨层。**

---

## 三、文件命名规范

| 位置 | 命名规则 | 示例 |
|------|---------|------|
| 源码文件 | 小写，下划线 | `config_simple.py`、`user_profile.py` |
| 模型文件 | `models.py`（每个子包统一） | `pipeline/models.py` |
| 入口/门面 | `core.py` 或与包同名 | `pipeline/core.py` |
| 工具函数 | `utils.py` 或具体描述 | `ui_utils.py` |
| 测试文件 | `test_<被测模块>.py` | `test_config_simple.py` |
| 脚本文件 | 动词_名词 | `migrate_v3_to_v4.py` |

**禁止的命名模式：**
- 不使用 `new_`、`v2_`、`final_` 等修饰前缀
- 不使用 `temp_`、`backup_`、`old_` 等临时后缀
- `*_simple.py` 仅用于表示"无外部依赖的纯实现"（如 `config_simple.py` 表示无热重载依赖的基础配置）

---

## 四、代码文件结构规范

每个 `.py` 文件按如下顺序组织：

```python
"""模块用途（一句话）

可选的扩展说明。
"""

# 1. 标准库导入
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# 2. 第三方库导入（空一行分隔）
from pydantic import BaseModel
import chromadb

# 3. 本地导入（空一行分隔）
from huaqi_src.core.config_simple import get_config
from huaqi_src.core.config_paths import get_data_dir

# 4. 常量定义（全大写）
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

# 5. 数据模型（dataclass / Pydantic / TypedDict / Enum）
class MyStatus(Enum):
    ...

@dataclass
class MyModel:
    ...

# 6. 主要类定义
class MyService:
    ...

# 7. 模块级函数（工厂函数、工具函数）
def create_service() -> MyService:
    ...

# 8. 单例变量 + 获取函数（如需要）
_instance: Optional[MyService] = None

def get_service() -> MyService:
    global _instance
    if _instance is None:
        _instance = MyService()
    return _instance
```

---

## 五、代码规范细则

### 5.1 命名约定

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `UserProfile`、`ChromaClient` |
| 函数/方法名 | snake_case，动词开头 | `get_config()`、`add_memory()` |
| 变量名 | snake_case | `user_id`、`persist_directory` |
| 常量 | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT`、`MAX_RETRIES` |
| 私有成员 | 单下划线前缀 | `_scheduler`、`_on_job_executed()` |
| 模块级单例 | 下划线前缀 | `_chroma_client`、`_config` |
| 意图常量 | `INTENT_` 前缀 | `INTENT_CHAT`、`INTENT_DIARY` |

### 5.2 类型注解

所有公开函数和方法必须有完整类型注解：

```python
# 正确
def search(
    self,
    query: str,
    top_k: int = 5,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:

# 错误 - 缺少注解
def search(self, query, top_k=5):
```

- 使用 `Optional[X]` 表示可为 None 的参数
- 复杂返回类型优先定义 dataclass 或 TypedDict，而非裸 `Dict`
- 不强制要求私有方法有注解，但推荐加

### 5.3 文档字符串

类和公开方法必须有 docstring，格式如下：

```python
def add(self, doc_id: str, content: str, metadata: Optional[Dict] = None) -> bool:
    """添加文档到向量库

    Args:
        doc_id: 文档唯一 ID
        content: 文档内容
        metadata: 可选的元数据，如 {"date": "2026-03-29", "type": "diary"}

    Returns:
        bool: 是否成功添加
    """
```

- 第一行：一句话说明功能，不超过 80 字符
- 空一行后写 Args/Returns（只在参数含义不明显时写）
- 不在 docstring 里重复函数签名已有的信息

### 5.4 异常处理

```python
# 推荐：明确的 try-except，失败返回默认值/False/None
def delete(self, doc_id: str) -> bool:
    try:
        self.collection.delete(ids=[doc_id])
        return True
    except Exception as e:
        print(f"删除失败: {e}")
        return False

# 禁止：裸 except，或捕获异常后不处理
try:
    ...
except:
    pass
```

对于无法恢复的初始化错误，允许直接抛出异常（不 catch）。

### 5.5 单例模式

需要全局唯一实例时，统一使用模块级变量 + 获取函数：

```python
_instance: Optional[MyService] = None

def get_my_service() -> MyService:
    """获取 MyService 单例"""
    global _instance
    if _instance is None:
        _instance = MyService()
    return _instance
```

不使用类方法实现单例，不使用装饰器单例。

### 5.6 数据模型选择

| 场景 | 推荐方式 |
|------|---------|
| LangGraph 状态定义 | `TypedDict` |
| 内部数据传输对象（无验证需求） | `@dataclass` + `field(default_factory=...)` |
| 配置类（需要验证、环境变量读取） | `pydantic.BaseModel` 或 `pydantic_settings.BaseSettings` |
| 状态枚举 | `Enum`（值使用小写字符串） |
| API 响应/请求（需序列化） | `pydantic.BaseModel` |

```python
# dataclass 示例（正确）
@dataclass
class ContentItem:
    id: str
    content: str
    tags: List[str] = field(default_factory=list)   # 可变默认值用 field
    created_at: datetime = field(default_factory=datetime.now)

# 错误 - 可变默认值直接赋值会导致共享
@dataclass
class ContentItem:
    tags: List[str] = []   # 禁止
```

### 5.7 延迟初始化

对于耗资源的依赖（数据库连接、模型加载等），使用 `@property` 延迟初始化：

```python
class MyClient:
    def __init__(self):
        self._connection: Optional[Connection] = None

    @property
    def connection(self) -> Connection:
        if self._connection is None:
            self._connection = create_connection()
        return self._connection
```

---

## 六、`__init__.py` 规范

每个子包必须有 `__init__.py`，内容包括：

1. 模块 docstring（说明该包的职责）
2. 公开 API 的导出（`from .xxx import Yyy`）
3. `__all__` 列表（按分组列出，加注释说明分组）

```python
"""内容流水线模块

支持 X、RSS 等内容源采集，自动处理并发布到目标平台。
"""

from .models import ContentItem, ContentStatus, PlatformType
from .core import ContentPipeline, create_default_pipeline

__all__ = [
    # 数据模型
    "ContentItem",
    "ContentStatus",
    "PlatformType",
    # 流水线
    "ContentPipeline",
    "create_default_pipeline",
]
```

**`core/` 模块例外**：当前采用平铺结构，无 `__init__.py`，各文件直接按需导入。若未来拆分子包，需补充 `__init__.py`。

---

## 七、测试文件组织

```
tests/
├── __init__.py
├── conftest.py           # pytest fixtures（共享的 mock、临时目录等）
├── unit/                 # 单元测试（不依赖外部服务）
│   ├── __init__.py
│   ├── test_config_simple.py
│   ├── test_user_profile.py
│   └── test_pipeline_models.py
├── integration/          # 集成测试（依赖数据库、文件系统）
│   ├── __init__.py
│   └── test_chroma_client.py
├── e2e/                  # 端到端测试（完整流程）
│   └── test_chat_flow.py
└── fixtures/             # 测试数据文件
```

**规则：**
- 所有测试放在 `tests/` 目录下，不得散落在根目录
- 测试文件命名：`test_<被测模块名>.py`
- 测试类命名：`Test<被测类名>`，测试函数命名：`test_<场景描述>`
- 每个 unit test 必须能独立运行，不依赖顺序

---

## 八、新建文件检查清单

在新建任何 `.py` 文件前，请确认：

- [ ] 文件应放在哪个模块？职责是否符合该模块的边界（参见第二节）？
- [ ] 文件名是否符合第三节的命名规范？
- [ ] 是否已有类似功能的文件，可以扩展而非新建？
- [ ] 文件头部是否有 docstring 说明用途？
- [ ] Import 是否按标准库 → 第三方 → 本地的顺序排列？
- [ ] 所有公开函数是否有类型注解？
- [ ] 如果是新子包，是否已创建 `__init__.py` 并导出公开 API？
- [ ] 是否需要在 `tests/` 下新建对应的测试文件？

---

## 九、当前已知的技术债务

所有已知技术债务已全部完成。新增问题请按以下格式追加：

| 问题 | 位置 | 优先级 | 处理方向 |
|------|------|--------|---------|

---

**文档版本**: v1.2
**最后更新**: 2026-03-29
