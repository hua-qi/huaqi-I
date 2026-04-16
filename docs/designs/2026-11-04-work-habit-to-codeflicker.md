# 工作习惯分析与 Codeflicker 个性化注入

**Date:** 2026-11-04

## Context

huaqi-growing 已具备从 codeflicker 对话记录中采集数据并写入工作日志的能力，Telos 引擎也能从 RawSignal 中蒸馏成长洞察。但目前这些积累对 codeflicker 本身是单向的——huaqi 从 codeflicker 学，codeflicker 却不知道用户的工作偏好。

目标：让 huaqi 分析用户的工作习惯，并将结论自动注入 `~/.codeflicker/AGENTS.md`，使 codeflicker 在所有项目中都能感知用户的技术决策倾向、写作风格和已知盲区，从而提升工作效率。

## Discussion

### 数据源范围

用户的工作习惯分散在多处，且随着就职公司的变化，部分数据源需要替换。因此数据源采用**注册表模式**（与现有 DataProvider 同构），每个数据源是独立的可插拔组件。

确认纳入的数据源：

| 数据源 | 说明 | 可替换性 |
|--------|------|--------|
| codeflicker 对话记录 | 已有 `cli_chats/` 目录 | 稳定，不随公司变化 |
| huaqi-growing `docs/` 目录 | 项目自身的设计文档、方案 | 稳定 |
| 公司内部文档系统 | 如快手内部 docs 系统 | **随公司变化，需替换** |

排除：本地 `.md` 文档扫描（范围过宽，噪音多，YAGNI）。

### 工作习惯维度

初始 6 个维度，由 Telos 通过 `work_style` 自定义维度承载。`work_style` 维度在 `WorkSignalIngester` 首次运行时自动创建（若不存在），初始 content 为空占位内容，置信度 0.4。

LLM 在处理工作信号时，通过 `Step1Output.new_dimension_hint` 字段可以提示发现了超出现有维度的新特征。**但当前 `DistillationPipeline` 并未消费 `new_dimension_hint`**，工作信号只会更新已存在的维度。动态维度自动发现属于 `DistillationPipeline` 的待实现项（见下方补充说明）。

| 维度 | 说明 |
|------|------|
| 写作与表达风格 | 先结论还是先背景？结构化列表还是叙述式？ |
| 代码风格偏好 | 命名习惯、层次结构倾向、注释密度等 |
| 工作技能界定 | 擅长系统设计还是具体实现？偏前端/后端/架构？ |
| 自评优缺点与盲区 | 自我提到过的优点/弱点，以及系统观察到的未意识到的模式 |
| 技术决策倾向 | 实用优先还是优雅优先？引入新依赖的门槛？ |
| 工作节奏与时间模式 | 深夜高产？上午写文档？习惯的 session 时长？ |

### 与 Telos 的融合方案

不新建独立的 `UserWorkStyle` 模型，而是**将工作数据作为新信号来源注入 Telos**，工作习惯自然沉淀为 Telos 中的 `work_style` 自定义维度（Middle 层）。

理由：
- Telos 已有版本化、置信度、动态维度、信号溯源等能力，无需重复建设
- `work_style` 的稳定性与 `strategies`、`goals` 同属 Middle 层，完全契合
- 换公司时只换数据源插件，Telos 维度结构不变

### 注入 Codeflicker 的方式

codeflicker 全局规则文件路径：**`~/.codeflicker/AGENTS.md`**

- 该文件在所有 codeflicker 会话启动时自动加载，与项目级 `AGENTS.md` 合并生效
- huaqi 只维护其中的 `## My Work Style` 段落，其余内容（如用户自己写的规则）保留不动
- 每次 Telos 的 `work_style` 维度发生变化时，自动触发重写该段落

### 触发机制

整条链路的触发是**事件驱动**的：

```
codeflicker 会话结束 → CLIChatWatcher 处理文件
  → WorkSignalIngester（新增 hook）拉取增量信号
  → 注入 DistillationPipeline
  → TelosEngine 更新 work_style 维度
  → CLAUDEmdWriter 重写 ~/.codeflicker/AGENTS.md 中的 ## My Work Style
```

## Approach

1. 新增 `WorkDataSource` 抽象基类和初始三个实现
2. 新增 `WorkSignalIngester`，作为 CLIChatWatcher 处理完文件后的新 hook
3. 扩展 `SourceType` 枚举，添加 `WORK_DOC` 类型
4. `CLAUDEmdWriter` 监听 Telos `work_style` 维度变化并重写 AGENTS.md

## Architecture

### 总体数据流

```
WorkDataSource 注册表
  ├── CodeflickerSource      → 读取 cli_chats/ 目录
  ├── HuaqiDocsSource        → 读取 huaqi-growing/docs/ 目录
  └── KuaishouDocsSource     → 内部文档系统 API（可替换）
          ↓
WorkSignalIngester.ingest()
  聚合所有数据源的增量内容
  包装为 RawSignal(source_type=SourceType.WORK_DOC)
          ↓
现有 DistillationPipeline.process()（不改动）
          ↓
TelosEngine → work_style 自定义维度更新（Middle 层）
          ↓
CLAUDEmdWriter.sync()（Telos 变化回调）
  读取 Telos work_style + strategies + shadows 维度
  重写 ~/.codeflicker/AGENTS.md 中 ## My Work Style 段落
```

### WorkDataSource 注册表

**文件：** `huaqi_src/layers/data/collectors/work_data_source.py`（新增）

```python
class WorkDataSource(ABC):
    name: str
    source_type: str  # 标识来源，用于 RawSignal.metadata

    @abstractmethod
    def fetch_documents(self, since: Optional[datetime] = None) -> List[str]:
        """返回增量文档内容列表，since 为上次处理时间"""
        pass
```

注册机制与 DataProvider 完全一致：

```python
_work_source_registry: list = []

def register_work_source(source: WorkDataSource) -> None: ...
def get_work_sources() -> list: ...
```

**初始三个实现：**

| 类 | 文件 | 数据来源 |
|----|------|--------|
| `CodeflickerSource` | `collectors/work_sources/codeflicker.py` | `get_cli_chats_dir()` 目录下 codeflicker 的 .md 文件 |
| `HuaqiDocsSource` | `collectors/work_sources/huaqi_docs.py` | `huaqi-growing/docs/` 目录下所有 .md 文件 |
| `KuaishouDocsSource` | `collectors/work_sources/kuaishou_docs.py` | 内部文档系统 HTTP API |

### WorkSignalIngester

**文件：** `huaqi_src/layers/data/collectors/work_signal_ingester.py`（新增）

```python
class WorkSignalIngester:
    def __init__(self, signal_store: RawSignalStore, pipeline: DistillationPipeline,
                 telos_manager: TelosManager): ...

    async def ingest(self, since: Optional[datetime] = None) -> int:
        """从所有注册的 WorkDataSource 拉取文档，注入 DistillationPipeline。返回处理条数。"""
        self._ensure_work_style_dimension()
        for source in get_work_sources():
            docs = source.fetch_documents(since=since)
            for doc in docs:
                signal = RawSignal(
                    source_type=SourceType.WORK_DOC,
                    content=doc,
                    metadata={"work_source": source.name},
                )
                await self.pipeline.process(signal)

    def _ensure_work_style_dimension(self) -> None:
        """若 work_style 维度不存在，自动创建。"""
        try:
            self._telos_manager.get("work_style")
        except DimensionNotFoundError:
            self._telos_manager.create_custom(
                name="work_style",
                layer=DimensionLayer.MIDDLE,
                initial_content="（待积累）",
            )
```

**接入点：** `CLIChatWatcher._process_codeflicker_session()` 在现有 `WorkLogWriter.write()` 调用之后，添加：

```python
await self._work_signal_ingester.ingest(since=last_processed_at)
```

### CLAUDEmdWriter

**文件：** `huaqi_src/layers/capabilities/codeflicker/claude_md_writer.py`（新增）

```python
class CLAUDEmdWriter:
    AGENTS_MD_PATH = Path.home() / ".codeflicker" / "AGENTS.md"
    SECTION_HEADER = "## My Work Style"

    def __init__(self, telos_manager: TelosManager): ...

    def sync(self) -> None:
        """从 Telos 读取 work_style 等维度，重写 AGENTS.md 中的 ## My Work Style 段落。"""
        content = self._build_work_style_section()
        self._upsert_section(self.AGENTS_MD_PATH, self.SECTION_HEADER, content)

    def _build_work_style_section(self) -> str:
        """读取 work_style / strategies / shadows 维度，生成 Markdown 段落。"""
        ...

    def _upsert_section(self, path: Path, header: str, content: str) -> None:
        """读取已有文件，替换指定 header 下的段落，保留其他内容。若文件不存在则新建。"""
        ...
```

**触发时机：** TelosManager.update() 在写入 `work_style` 维度后，通过回调触发 `CLAUDEmdWriter.sync()`。

### SourceType 扩展

**文件：** `huaqi_src/layers/data/raw_signal/models.py`

新增枚举值：

```python
WORK_DOC = "work_doc"   # 工作文档（技术方案、设计文档、内部文档等）
```

### 生成的 AGENTS.md 段落示例

```markdown
## My Work Style

> 由 huaqi-growing 自动维护，最后更新：2026-11-04

### 写作与表达
先结论后背景。偏好结构化列表，少用长段落。技术方案通常先给出 Context → Discussion → Approach → Architecture 的结构。

### 代码偏好
命名重语义。倾向三层架构，排斥「万能 core 目录」。引入新依赖前先检查项目已有实现。

### 技术决策
实用优先，但对架构整洁度有高要求。设计新功能时会先对比 2-3 个方案再选择。

### 工作节奏
深夜高产，上午适合写文档，下午适合写代码。

### 已知盲区（请主动提醒我）
- 提醒我在方案中加「失败降级策略」
- 提醒我评估迁移成本，不只是新增成本
```

### 新增 / 修改文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `layers/data/collectors/work_data_source.py` | 新增 | WorkDataSource 抽象基类 + 注册表 |
| `layers/data/collectors/work_sources/codeflicker.py` | 新增 | CodeflickerSource 实现 |
| `layers/data/collectors/work_sources/huaqi_docs.py` | 新增 | HuaqiDocsSource 实现 |
| `layers/data/collectors/work_sources/kuaishou_docs.py` | 新增 | KuaishouDocsSource 实现（公司专属，可替换） |
| `layers/data/collectors/work_signal_ingester.py` | 新增 | WorkSignalIngester，从数据源到 DistillationPipeline |
| `layers/data/collectors/cli_chat_watcher.py` | 微调 | `_process_codeflicker_session()` 末尾添加 ingester hook |
| `layers/data/raw_signal/models.py` | 微调 | `SourceType` 新增 `WORK_DOC = "work_doc"` |
| `layers/capabilities/codeflicker/claude_md_writer.py` | 新增 | 读取 Telos 写入 `~/.codeflicker/AGENTS.md` |
| `layers/growth/telos/manager.py` | 微调 | `update()` 在写入 `work_style` 维度后触发 CLAUDEmdWriter 回调 |

### 依赖关系

```
KuaishouDocsSource（可替换）
        ↓
WorkDataSource 注册表
        ↓
WorkSignalIngester ← CLIChatWatcher hook（已有）
        ↓
DistillationPipeline（已有，不改动）
        ↓
TelosEngine → work_style 维度（已有，微调回调）
        ↓
CLAUDEmdWriter → ~/.codeflicker/AGENTS.md
```

## 设计决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 工作习惯存储位置 | Telos work_style 自定义维度 | 复用版本化、置信度、动态维度能力，无需重复建设 |
| 数据源扩展机制 | WorkDataSource 注册表（同构 DataProvider） | 换公司时只替换 KuaishouDocsSource，其余不动 |
| 触发机制 | 事件驱动（CLIChatWatcher hook） | 与现有 WorkLogWriter hook 模式一致，无需新增定时任务 |
| AGENTS.md 路径 | `~/.codeflicker/AGENTS.md` | codeflicker 全局规则文件，所有项目会话均自动加载 |
| 段落维护策略 | 只更新 `## My Work Style` 段落 | 不破坏用户已有的自定义规则 |
| 排除本地 .md 扫描 | 不实现 | 范围过宽噪音多，YAGNI |
| 新维度发现 | LLM 自动发现并写入 | 利用 Telos 已有动态维度机制，无需用户确认 |

## Telos 代码现状与本功能的关系

本功能依赖 Telos 作为工作习惯的存储和分析引擎。经 2026-11-04 代码核查，此前验收清单中标注的 7 条"未实现项"**均已完成代码实现**，当前均处于"待正式验收测试执行"状态。

### 与本功能相关的 Telos 能力现状

| 能力 | 代码状态 | 对本功能的影响 |
|------|---------|--------------|
| `PeoplePipeline` | ✅ 已实现 | 无影响（工作习惯分析不涉及人物关系） |
| `search_person_tool` 注入 | ✅ 已实现 | 无影响 |
| `search_memory_tool` + `search_by_embedding` | ✅ 已实现（内存余弦相似度） | **正向影响**：Agent 可检索历史工作信号做参考 |
| asyncio 全链路 | ✅ 已实现 | 工作信号通过 `DistillationPipeline` 并行处理 |
| `new_dimension_hint` 消费 | ❌ **仍未实现** | **直接影响**：工作信号触发的超出 `work_style` 之外的新维度无法自动创建 |

### 唯一仍未实现项：new_dimension_hint 处理

**现状：** `step1_analyze()` 输出 `new_dimension_hint`，但 `DistillationPipeline.process()` 完全忽略该字段。

**影响：** 工作信号中如果触发了超出 `work_style` 之外的新维度（如 LLM 发现"项目管理习惯"），当前只有 hint 输出，不会自动创建维度文件，`process_dimension()` 调用 `manager.get()` 时会抛 `DimensionNotFoundError` 被静默吞掉。

**设计方案：** 在 `DistillationPipeline.process()` 的 Step1 之后，消费 `new_dimension_hint`：

```python
if step1_result.new_dimension_hint:
    hint = step1_result.new_dimension_hint
    try:
        self._mgr.get(hint)
    except DimensionNotFoundError:
        self._mgr.create_custom(
            name=hint,
            layer=DimensionLayer.SURFACE,
            initial_content="（待积累）",
        )
    step1_result.dimensions.append(hint)
```

**改动文件：** `huaqi_src/layers/data/raw_signal/pipeline.py`，`process()` 方法，Step1 调用之后约第 38 行。

**注意：** `WorkSignalIngester._ensure_work_style_dimension()` 仍然保留——它负责在系统首次运行时预建 `work_style`，与 hint 处理互补，不冲突。

## 实施顺序

```
阶段 1（Telos 已有能力已足够，可独立启动）
  ├── WorkDataSource 注册表 + 三个数据源实现
  ├── WorkSignalIngester（含 _ensure_work_style_dimension）
  ├── SourceType.WORK_DOC 扩展
  ├── CLIChatWatcher hook 接入
  └── CLAUDEmdWriter → ~/.codeflicker/AGENTS.md

阶段 2（提升 work_style 动态维度发现能力）
  └── DistillationPipeline 消费 new_dimension_hint
      （pipeline.py 约 38 行处，3 行代码改动）
```

## 补充说明

### new_dimension_hint 的现状

`TelosEngine.step1_analyze()` 的 prompt 已包含 `new_dimension_hint` 输出字段，当 LLM 判断信号不属于现有任何维度时会填充该字段。但 `DistillationPipeline.process()` 目前**完全忽略该字段**，既不自动创建新维度，也不提示用户。

本设计阶段 1 不强依赖该能力，`work_style` 维度由 `WorkSignalIngester._ensure_work_style_dimension()` 预先保证存在。阶段 2 打通该逻辑后，工作信号中 LLM 发现的其他工作特征维度（如"项目管理习惯"）将能自动创建并被后续信号持续更新。
