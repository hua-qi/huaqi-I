# 报告 DataProvider 注册表

## 概述

用 DataProvider 注册表解耦报告生成系统。各数据模块各自实现 `DataProvider` 并自注册，报告类通过 `build_context()` 统一收集上下文，无需感知具体数据来源。

---

## 设计思路

原有报告类（晨报、日报、周报、季报）各自在 `_build_context()` 内硬编码数据读取逻辑，每次新增数据模块都需修改 4 个报告文件。

引入注册表后：
- **数据模块**只管实现自己的 `DataProvider`，在文件末尾自注册
- **报告类**只管调用 `build_context(report_type, date_range)`，不关心数据从哪来
- 新增数据模块接入报告系统，**无需修改任何现有报告文件**

---

## 模块结构

```
huaqi_src/reports/
├── context_builder.py          # 统一上下文构建入口
└── providers/
    ├── __init__.py             # DataProvider 基类 + 全局注册表
    ├── world.py                # 世界新闻
    ├── diary.py                # 日记
    ├── work_log.py             # 工作日志（codeflicker 会话）
    ├── people.py               # 人际关系
    ├── learning.py             # 学习进度
    ├── growth.py               # 成长目标
    ├── events.py               # 事件流
    └── weekly_reports.py       # 周报归档（供季报使用）
```

---

## 实现细节

### DataProvider 基类与注册表

```python
# huaqi_src/reports/providers/__init__.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

@dataclass
class DateRange:
    start: date
    end: date

class DataProvider(ABC):
    name: str
    priority: int = 50
    supported_reports: list  # 填 ["*"] 表示适用所有报告类型

    @abstractmethod
    def get_context(self, report_type: str, date_range: DateRange) -> "str | None":
        pass

_registry: list = []

def register(provider: DataProvider) -> None:
    _registry.append(provider)

def get_providers(report_type: str) -> list:
    return sorted(
        [p for p in _registry if report_type in p.supported_reports or "*" in p.supported_reports],
        key=lambda p: p.priority,
    )
```

### ContextBuilder

```python
# huaqi_src/reports/context_builder.py
from huaqi_src.reports.providers import DateRange, get_providers

def build_context(report_type: str, date_range: DateRange) -> str:
    parts = [
        ctx
        for p in get_providers(report_type)
        if (ctx := p.get_context(report_type, date_range))
    ]
    return "\n\n".join(parts) if parts else "暂无上下文数据。"
```

### Provider 实现模式

每个 Provider 文件末尾用 `try/except` 保护的自注册：

```python
try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(XxxProvider(_data_dir))
except Exception:
    pass
```

报告类在 `__init__` 中调用 `_register_providers()`，用正确的 `data_dir` 覆盖模块级自注册：

```python
def _register_providers(self) -> None:
    from huaqi_src.reports.providers import _registry, register
    from huaqi_src.reports.providers.world import WorldProvider
    # 先清除同名旧实例，再重新注册
    for p in list(_registry):
        if p.name in ("world", ...):
            _registry.remove(p)
    register(WorldProvider(self._data_dir))
```

---

## 各 Provider 说明

| Provider | 数据来源 | 适用报告 | 优先级 |
|----------|---------|---------|--------|
| `WorldProvider` | `data_dir/world/YYYY-MM-DD.md` | morning, daily | 10 |
| `DiaryProvider` | `data_dir/memory/diary/YYYY-MM-DD.md` | `*` | 20 |
| `WorkLogProvider` | `data_dir/work_logs/YYYY-MM/YYYYMMDD_*.md` | daily | 25 |
| `LearningProvider` | `data_dir/learning/courses/` + `sessions/` | daily, weekly, quarterly | 30 |
| `PeopleProvider` | `data_dir/people/*.md` | `*` | 40 |
| `GrowthProvider` | `data_dir/memory/growth.yaml` | weekly, quarterly | 50 |
| `EventsProvider` | `data_dir/events.db`（SQLite） | daily, weekly | 60 |
| `WeeklyReportsProvider` | `data_dir/reports/weekly/*.md` | quarterly | 70 |

`DateRange` 的传入规则：
- 晨报 / 日报：`start = end = today`
- 周报：`start = today - 6天，end = today`
- 季报：`start = today - 13周，end = today`

`events.db` 的字段说明：`timestamp` 为 Unix 整数时间戳，非 ISO 字符串，`EventsProvider` 按时间戳范围过滤。

---

## 扩展方式

新增数据模块接入报告，只需 5 步：

1. 在 `huaqi_src/reports/providers/` 下新建文件
2. 继承 `DataProvider`，设置 `name`、`priority`、`supported_reports`
3. 实现 `get_context()`，返回 `str | None`
4. 文件末尾加 `try/except` 自注册
5. 在对应报告类的 `_register_providers()` 中添加一行 import + register

无需修改任何报告文件的 Prompt 或 `run()` 方法。

---

## 相关文件

- `huaqi_src/layers/capabilities/reports/providers/__init__.py` — DataProvider 基类、DateRange、注册表
- `huaqi_src/layers/capabilities/reports/context_builder.py` — build_context() 入口
- `huaqi_src/layers/capabilities/reports/providers/world.py` — WorldProvider
- `huaqi_src/layers/capabilities/reports/providers/diary.py` — DiaryProvider
- `huaqi_src/layers/capabilities/reports/providers/work_log.py` — WorkLogProvider
- `huaqi_src/layers/capabilities/reports/providers/people.py` — PeopleProvider
- `huaqi_src/layers/capabilities/reports/providers/learning.py` — LearningProvider
- `huaqi_src/layers/capabilities/reports/providers/growth.py` — GrowthProvider
- `huaqi_src/layers/capabilities/reports/providers/events.py` — EventsProvider
- `huaqi_src/layers/capabilities/reports/providers/weekly_reports.py` — WeeklyReportsProvider
- `huaqi_src/layers/capabilities/reports/daily_report.py` — 已注册 WorkLogProvider
- `tests/unit/layers/capabilities/reports/test_providers.py` — Provider 单元测试
- `tests/unit/layers/capabilities/reports/test_daily_report.py` — DailyReportAgent 单元测试

---

**文档版本**: v1.2
**最后更新**: 2026-04-15
