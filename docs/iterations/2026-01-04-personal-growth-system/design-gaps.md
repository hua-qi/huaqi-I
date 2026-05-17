# 设计缺口补充文档

> 本文档补充「个人成长系统完整设计文档」中遗留的 6 个设计缺口，是 TDD 开始前的最后一份设计文档。

---

## 缺口 1：抽象接口方法签名

所有 I/O 必须通过以下抽象接口，实现类放在 `huaqi_src/config/adapters/` 下。

### StorageAdapter（raw_signal 读写）

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter

class StorageAdapter(ABC):

    @abstractmethod
    def save(self, signal: RawSignal) -> None: ...

    @abstractmethod
    def get(self, signal_id: str) -> Optional[RawSignal]: ...

    @abstractmethod
    def query(self, filter: RawSignalFilter) -> List[RawSignal]: ...

    @abstractmethod
    def mark_processed(self, signal_id: str) -> None: ...

    @abstractmethod
    def mark_distilled(self, signal_id: str) -> None: ...

    @abstractmethod
    def count(self, filter: RawSignalFilter) -> int: ...
```

`RawSignalFilter` 是 Pydantic 模型，包含：

```python
class RawSignalFilter(BaseModel):
    user_id: str
    source_type: Optional[str] = None
    processed: Optional[int] = None        # 0 or 1
    distilled: Optional[int] = None        # 0 or 1
    since: Optional[datetime] = None       # timestamp >= since
    until: Optional[datetime] = None       # timestamp <= until
    limit: int = 100
    offset: int = 0
```

### VectorAdapter（向量检索）

```python
from abc import ABC, abstractmethod
from typing import List
from huaqi_src.layers.data.memory.models import VectorDocument, VectorQuery, VectorResult

class VectorAdapter(ABC):

    @abstractmethod
    def upsert(self, doc: VectorDocument) -> None: ...

    @abstractmethod
    def upsert_batch(self, docs: List[VectorDocument]) -> None: ...

    @abstractmethod
    def query(self, q: VectorQuery) -> List[VectorResult]: ...

    @abstractmethod
    def delete(self, doc_id: str, user_id: str) -> None: ...
```

相关 Pydantic 模型：

```python
class VectorDocument(BaseModel):
    id: str                        # signal_id 或其他唯一标识
    user_id: str
    content: str                   # 被向量化的文本
    metadata: dict = {}            # 原始信号的摘要元数据，用于过滤

class VectorQuery(BaseModel):
    user_id: str
    text: str                      # 查询文本
    top_k: int = 5
    filter: dict = {}              # ChromaDB where 过滤条件

class VectorResult(BaseModel):
    id: str
    content: str
    metadata: dict
    score: float
```

### SchedulerAdapter（定时任务注册）

```python
from abc import ABC, abstractmethod
from typing import Callable

class SchedulerAdapter(ABC):

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def add_interval_job(
        self,
        func: Callable,
        seconds: int,
        job_id: str,
    ) -> None: ...

    @abstractmethod
    def add_cron_job(
        self,
        func: Callable,
        cron_expr: str,       # "0 8 * * *" 格式
        job_id: str,
    ) -> None: ...

    @abstractmethod
    def remove_job(self, job_id: str) -> None: ...
```

### InterfaceAdapter（输出通道）

```python
from abc import ABC, abstractmethod
from typing import Optional

class InterfaceAdapter(ABC):

    @abstractmethod
    def send_message(self, text: str, user_id: str) -> None: ...

    @abstractmethod
    def send_question(
        self,
        text: str,
        user_id: str,
        options: Optional[list[str]] = None,
    ) -> None: ...

    @abstractmethod
    def display_progress(self, message: str) -> None: ...
```

---

## 缺口 2：AgentState 新结构

将 `personality_context: Optional[str]` 替换为三个字段，对应 System Prompt 的 Part2/Part3/Part4：

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

    user_id: str

    # 原 personality_context 拆分为：
    telos_snapshot: Optional[str]           # Part2: TELOS INDEX.md 摘要（成长层快照）
    relevant_history: Optional[List[str]]   # Part3: ChromaDB 语义检索结果片段
    interaction_mode: Optional[str]         # Part4: 当前对话模式（chat/distill/report/onboarding）

    intent: Optional[str]
    intent_confidence: float
    workflow_data: Dict[str, Any]
    interrupt_requested: bool
    interrupt_reason: Optional[str]
    interrupt_data: Optional[Dict[str, Any]]
    error: Optional[str]
    retry_count: int
    response: Optional[str]
```

`create_initial_state` 对应更新：

```python
def create_initial_state(
    user_id: str = "default",
    telos_snapshot: Optional[str] = None,
    relevant_history: Optional[List[str]] = None,
    interaction_mode: str = "chat",
) -> AgentState: ...
```

**interaction_mode 取值**：

| 值 | 含义 |
|---|---|
| `chat` | 日常对话，TELOS 作背景 |
| `distill` | 主动触发信号提炼 |
| `report` | 生成周报/月报 |
| `onboarding` | 冷启动问卷阶段 |

---

## 缺口 3：错误类型体系

文件位置：`huaqi_src/config/errors.py`（全局基类） + 各层自己的 `errors.py`。

### 继承树

```
HuaqiError（基类）
├── StorageError               # 数据库读写失败
│   ├── SignalNotFoundError     # 查无此 signal_id
│   └── SignalDuplicateError    # 重复写入同一 id
├── VectorError                # 向量库操作失败
│   └── VectorUpsertError
├── TelosError                 # TELOS 文件操作失败
│   ├── DimensionNotFoundError # 维度文件不存在
│   └── DimensionParseError    # frontmatter 解析失败
├── DistillationError          # 信号提炼管道失败
│   ├── AnalysisError          # Step1~3 AI 调用失败
│   └── UpdateGenerationError  # Step4 生成失败
├── SchedulerError             # 定时任务注册/运行失败
├── InterfaceError             # 输出通道失败
├── AgentError                 # Agent 执行失败
│   └── IntentParseError       # 意图识别失败
└── UserError                  # 用户管理失败
    └── UserNotFoundError
```

### 基类定义

```python
class HuaqiError(Exception):
    def __init__(self, message: str, context: dict | None = None):
        super().__init__(message)
        self.context = context or {}
```

所有子类只需 `class XxxError(HuaqiError): pass`，需要附加上下文时通过 `context` 参数传递：

```python
raise SignalNotFoundError(
    f"Signal {signal_id} not found",
    context={"user_id": user_id, "signal_id": signal_id}
)
```

---

## 缺口 4：成长事件存储位置和表结构

**决策：同库（同一个 SQLite 文件），独立表 `growth_events`。**

原因：
- 成长事件和 RAW_SIGNAL 强关联（每个事件都有触发信号），同库可以做外键关联，避免跨库事务
- 不需要单独的成长事件数据库，降低运维复杂度

### 表结构

```sql
CREATE TABLE growth_events (
    id              TEXT PRIMARY KEY,      -- UUID
    user_id         TEXT NOT NULL,
    dimension       TEXT NOT NULL,         -- 触发维度，如 "beliefs"
    layer           TEXT NOT NULL,         -- "core" / "middle" / "surface"
    title           TEXT NOT NULL,         -- 成长事件标题
    narrative       TEXT NOT NULL,         -- 温暖的叙事描述（Agent 生成）
    old_content     TEXT,                  -- 变化前的维度内容
    new_content     TEXT NOT NULL,         -- 变化后的维度内容
    trigger_signals TEXT,                  -- JSON 数组，触发此事件的 signal_id 列表
    occurred_at     TEXT NOT NULL,         -- 成长发生的时间（ISO 8601）
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_growth_user_occurred ON growth_events(user_id, occurred_at DESC);
CREATE INDEX idx_growth_user_dimension ON growth_events(user_id, dimension);
CREATE INDEX idx_growth_user_layer ON growth_events(user_id, layer);
```

### 对应 Pydantic 模型

```python
class GrowthEvent(BaseModel):
    id: str                            # UUID
    user_id: str
    dimension: str
    layer: str                         # "core" / "middle" / "surface"
    title: str
    narrative: str
    old_content: Optional[str]
    new_content: str
    trigger_signals: List[str]         # signal_id 列表
    occurred_at: datetime
    created_at: datetime
```

---

## 缺口 5：向量化时机

**决策：独立定时任务，每 5 分钟批量处理，不阻塞写入主流程。**

原因：
- 同步向量化会阻塞 RAW_SIGNAL 写入，影响用户体验
- Step1 后立即向量化复杂度高，且 Step1 可能失败
- 定时批量处理实现简单，失败可重试，无状态

### 处理逻辑

```
定时任务每 5 分钟运行：
    查询 raw_signals WHERE vectorized = 0 LIMIT 50
    对每条 signal：
        生成向量化文本 = content + " " + summary（如果有）
        调用 VectorAdapter.upsert()
        标记 vectorized = 1
    如遇失败：记录日志，跳过该条，下次重试
```

需在 `raw_signals` 表新增一列：

```sql
ALTER TABLE raw_signals ADD COLUMN vectorized INTEGER DEFAULT 0;
CREATE INDEX idx_user_vectorized ON raw_signals(user_id, vectorized);
```

（在 Schema 初始化时一并创建，不需要 ALTER TABLE）

---

## 缺口 6：多用户 user_id 来源

**决策：本地 UUID4 生成，持久化到 `~/.huaqi/users.json`，CLI 通过 `--user` 切换。**

### users.json 结构

```json
{
  "current": "lianzimeng",
  "profiles": {
    "lianzimeng": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "lianzimeng",
      "created_at": "2026-01-04T00:00:00Z",
      "data_dir": "~/.huaqi/data/lianzimeng/"
    }
  }
}
```

- `name`：人类可读标识，用于目录命名和显示（不是 UUID）
- `id`：UUID4，用于数据库 `user_id` 字段（不可变）
- `data_dir`：该用户的数据根目录（TELOS 文件、SQLite、ChromaDB 都在此）

### 生成规则

1. 首次运行时，冷启动问卷前询问用户名（默认用系统用户名）
2. 生成 UUID4 作为内部 id
3. 写入 `~/.huaqi/users.json`

### CLI 切换

```bash
huaqi --user lianzimeng chat     # 切换到指定用户
huaqi user list                  # 列出所有 profiles
huaqi user create <name>         # 创建新用户
huaqi user switch <name>         # 切换默认用户（修改 current 字段）
```

### 数据隔离规则

| 资源 | 隔离方式 |
|---|---|
| SQLite | 同一文件，`WHERE user_id = ?` 隔离 |
| ChromaDB | 同一实例，metadata filter `user_id` 隔离 |
| TELOS 文件 | 各自独立目录 `~/.huaqi/data/{name}/telos/` |
| raw_files | 各自独立目录 `~/.huaqi/data/{name}/raw_files/` |

### UserContext 模型

```python
class UserProfile(BaseModel):
    id: str               # UUID4，不可变
    name: str             # 人类可读名，唯一
    created_at: datetime
    data_dir: Path        # 展开后的绝对路径

class UserContext(BaseModel):
    profile: UserProfile
    telos_dir: Path       # profile.data_dir / "telos"
    raw_files_dir: Path   # profile.data_dir / "raw_files"
    db_path: Path         # profile.data_dir / "signals.db"
    vector_dir: Path      # profile.data_dir / "vectors"
```

---

**文档版本**：v1.0
**创建时间**：2026-01-04
**解决缺口**：缺口 1~6（全部）
