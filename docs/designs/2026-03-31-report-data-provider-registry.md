# 报告系统数据提供者注册表

**Date:** 2026-03-31

## Context

当前报告系统（早报、日报、周报、季报）中，每个报告类通过硬编码方式读取特定目录（如 `memory/diary/`、`world/`、`people/`），数据来源分散且不完整，缺少学习记录、成长目标、事件流等模块的数据。随着后续新数据模块的不断加入，每次都需要手动修改多个报告文件，扩展成本高、容易遗漏。

核心诉求：
- **可扩展性**：新增数据模块后，报告自动纳入，无需改动报告代码
- **数据完整性**：所有用户数据模块（diary、learning、people、world、growth、events 等）都应参与报告生成
- **质量提升**：数据更全面，LLM 生成的报告内容更有深度

## Discussion

**探索了三种方案：**

1. **DataProvider 注册表（方案 A）**：每个数据模块实现标准 `DataProvider` 接口，在模块初始化时向全局注册表注册。报告生成时遍历注册表聚合上下文。解耦彻底，新模块只需实现接口并注册。

2. **约定目录扫描（方案 B）**：扫描 `data_dir` 下所有子目录，通用逻辑提取摘要。零代码新增，但对非文件型数据（SQLite）支持弱，摘要质量不如专属逻辑。

3. **Context Builder 管道（方案 C）**：多个独立 builder 串联成管道，按报告类型配置组合。渐进式改造友好，但无法共享状态。

**最终选择方案 A（注册表）**，理由：解耦最彻底，各模块对自身数据的理解最准确，且支持精细控制（优先级、适用报告类型）。

**自注册方式**：选择显式 import 触发（而非自动扫描 providers 目录），原因是依赖关系清晰、IDE 可追踪、不依赖文件系统约定。

## Approach

核心设计：**DataProvider 接口 + 全局注册表**。

每个数据模块实现 `DataProvider` 抽象类，声明自己支持的报告类型和优先级，并在模块文件末尾自注册到全局注册表。报告生成统一通过 `context_builder.build_context()` 收集所有相关模块的数据摘要，再交给 LLM 生成报告。

**新增数据模块的标准流程（规范）：**

> **重要**：后续所有新增的数据模块，如需参与报告生成，**必须遵循以下规范**：
>
> 1. 在 `huaqi_src/reports/providers/` 下新建对应的 provider 文件（如 `work_docs.py`）
> 2. 实现 `DataProvider` 抽象类，正确设置 `name`、`priority`、`supported_reports`
> 3. 在文件末尾调用 `register(YourProvider())` 完成自注册
> 4. 在 `context_builder.py` 中显式 import 该模块（一行代码）
> 5. 完成，无需修改任何报告文件

## Architecture

### 目录结构

```
huaqi_src/reports/
├── providers/
│   ├── __init__.py          # DataProvider 基类 + 全局注册表
│   ├── diary.py             # 日记数据
│   ├── learning.py          # 学习记录 + 课程进度
│   ├── people.py            # 人物关系图谱
│   ├── world.py             # 世界热点
│   ├── growth.py            # 成长目标 + 技能
│   └── events.py            # 事件流（SQLite）
├── context_builder.py       # 聚合所有 provider 的上下文
├── morning_brief.py         # 调用 context_builder，不再硬编码
├── daily_report.py
├── weekly_report.py
└── quarterly_report.py
```

### DataProvider 接口

```python
# providers/__init__.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

@dataclass
class DateRange:
    start: date
    end: date

class DataProvider(ABC):
    name: str                        # 模块标识，如 "diary"
    priority: int = 50               # 数字越小越靠前（Prompt 中位置越优先）
    supported_reports: list[str]     # 如 ["daily", "weekly"] 或 ["*"] 表示全部

    @abstractmethod
    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        """返回适合注入 Prompt 的文本摘要，无数据时返回 None"""

_registry: list[DataProvider] = []

def register(provider: DataProvider):
    _registry.append(provider)

def get_providers(report_type: str) -> list[DataProvider]:
    return sorted(
        [p for p in _registry if report_type in p.supported_reports or "*" in p.supported_reports],
        key=lambda p: p.priority
    )
```

### 自注册示例

```python
# providers/learning.py
class LearningProvider(DataProvider):
    name = "learning"
    priority = 30
    supported_reports = ["daily", "weekly", "quarterly"]

    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        # 读取 learning/sessions/ 和 courses/ 下的数据
        ...

register(LearningProvider())  # 文件末尾自注册
```

### ContextBuilder

```python
# context_builder.py
from huaqi_src.reports.providers import get_providers

# 显式 import 触发自注册（新增模块时在此加一行）
import huaqi_src.reports.providers.diary
import huaqi_src.reports.providers.learning
import huaqi_src.reports.providers.people
import huaqi_src.reports.providers.world
import huaqi_src.reports.providers.growth
import huaqi_src.reports.providers.events

def build_context(report_type: str, date_range: DateRange) -> str:
    return "\n\n".join(
        ctx for p in get_providers(report_type)
        if (ctx := p.get_context(report_type, date_range))
    )
```

### 数据流

```
定时触发（daemon 08:00）
    ↓
MorningBriefAgent.run()
    ↓
context_builder.build_context("morning", today)
    ↓
get_providers("morning") → [WorldProvider(p=10), DiaryProvider(p=20), PeopleProvider(p=40), LearningProvider(p=30), ...]
    ↓
每个 provider.get_context() → 文本摘要（None 则跳过）
    ↓
合并所有摘要 → 构造 LLM Prompt
    ↓
生成报告内容 → 写入 reports/daily/YYYY-MM-DD-morning.md
```

### 各模块 Provider 规划

| Provider | 读取数据 | 优先级 | 适用报告 |
|----------|---------|--------|---------|
| `WorldProvider` | `world/<date>.md` | 10 | morning, daily |
| `DiaryProvider` | `memory/diary/` | 20 | 全部 |
| `LearningProvider` | `learning/sessions/` + `courses/` | 30 | daily, weekly, quarterly |
| `PeopleProvider` | `people/` | 40 | 全部 |
| `GrowthProvider` | `memory/growth.yaml` | 50 | weekly, quarterly |
| `EventsProvider` | `events.db` | 60 | daily, weekly |
| `WeeklyReportProvider` | `reports/weekly/` | 70 | quarterly |
