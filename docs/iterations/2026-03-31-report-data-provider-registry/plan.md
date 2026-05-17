# Report Data Provider Registry Implementation Plan

**Goal:** 用 DataProvider 注册表解耦报告生成系统，让新数据模块无需修改报告代码即可自动参与报告生成。

**Architecture:** 定义抽象基类 `DataProvider` + 全局注册表，各数据模块各自实现并在文件末尾自注册；`context_builder.py` 统一收集所有 Provider 的摘要，报告类改为调用 `build_context()` 替代内嵌的 `_build_context()` 逻辑。

**Tech Stack:** Python 3.11+, ABC (标准库), dataclasses (标准库), pytest, PyYAML (已有), langchain-openai (已有)

---

## 背景知识

在动手之前，先了解项目结构：

- `huaqi_src/reports/` — 4 个报告类，每个都有 `_build_context()` 方法硬编码数据读取逻辑
- `huaqi_src/core/config_paths.py` — `get_learning_dir()`, `get_people_dir()`, `get_world_dir()` 等路径工具函数
- `huaqi_src/learning/progress_store.py` — `LearningProgressStore(base_dir)` 读取 `courses/` 和 `sessions/` 目录
- `huaqi_src/people/graph.py` — `PeopleGraph(data_dir)` 读取 `people/*.md` 文件
- `huaqi_src/collectors/document.py` — `HuaqiDocument` 数据模型
- 测试惯例：所有测试用 `tmp_path` 作为 `data_dir`，LLM 调用用 `patch.object` mock 掉
- 运行测试：`pytest tests/reports/ -v`

**报告类型字符串约定：** `"morning"`, `"daily"`, `"weekly"`, `"quarterly"`（与文件名对应）

---

## Task 1: 创建 DataProvider 基类和全局注册表

**Files:**
- Create: `huaqi_src/reports/providers/__init__.py`
- Create: `tests/reports/test_providers.py`

**Step 1: 写失败测试**

```python
# tests/reports/test_providers.py
from datetime import date
from huaqi_src.reports.providers import DataProvider, DateRange, register, get_providers, _registry


def test_register_and_get_providers():
    _registry.clear()

    class FakeProvider(DataProvider):
        name = "fake"
        priority = 10
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return "fake context"

    register(FakeProvider())
    providers = get_providers("daily")
    assert len(providers) == 1
    assert providers[0].name == "fake"


def test_get_providers_filters_by_report_type():
    _registry.clear()

    class MorningOnly(DataProvider):
        name = "morning_only"
        priority = 10
        supported_reports = ["morning"]

        def get_context(self, report_type, date_range):
            return "morning data"

    register(MorningOnly())
    assert len(get_providers("daily")) == 0
    assert len(get_providers("morning")) == 1


def test_wildcard_supported_reports():
    _registry.clear()

    class AllReports(DataProvider):
        name = "all"
        priority = 5
        supported_reports = ["*"]

        def get_context(self, report_type, date_range):
            return "all data"

    register(AllReports())
    assert len(get_providers("morning")) == 1
    assert len(get_providers("quarterly")) == 1


def test_get_providers_sorted_by_priority():
    _registry.clear()

    class LowPriority(DataProvider):
        name = "low"
        priority = 90
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return "low"

    class HighPriority(DataProvider):
        name = "high"
        priority = 10
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return "high"

    register(LowPriority())
    register(HighPriority())
    providers = get_providers("daily")
    assert providers[0].name == "high"
    assert providers[1].name == "low"
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_providers.py -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.reports.providers'`

**Step 3: 实现基类和注册表**

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
    supported_reports: list[str]

    @abstractmethod
    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        """返回适合注入 Prompt 的文本摘要，无数据时返回 None"""


_registry: list[DataProvider] = []


def register(provider: DataProvider) -> None:
    _registry.append(provider)


def get_providers(report_type: str) -> list[DataProvider]:
    return sorted(
        [p for p in _registry if report_type in p.supported_reports or "*" in p.supported_reports],
        key=lambda p: p.priority,
    )
```

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_providers.py -v
```

预期：4 tests passed

**Step 5: 提交**

```
git add huaqi_src/reports/providers/__init__.py tests/reports/test_providers.py
git commit -m "feat: add DataProvider base class and global registry"
```

---

## Task 2: 实现 WorldProvider

**Files:**
- Create: `huaqi_src/reports/providers/world.py`
- Modify: `tests/reports/test_providers.py`（追加测试）

**背景：** 世界新闻存储在 `data_dir/world/YYYY-MM-DD.md`。晨间和日报使用，优先级 10。

**Step 1: 追加失败测试**

```python
# 追加到 tests/reports/test_providers.py

import datetime
from pathlib import Path


def test_world_provider_returns_context(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    _registry.clear()

    import huaqi_src.reports.providers.world  # 触发自注册

    today = datetime.date.today()
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / f"{today.isoformat()}.md").write_text("AI 技术突破", encoding="utf-8")

    from huaqi_src.reports.providers import get_providers
    providers = get_providers("morning")
    assert len(providers) == 1

    date_range = DateRange(start=today, end=today)
    ctx = providers[0].get_context("morning", date_range)
    assert ctx is not None
    assert "AI 技术突破" in ctx


def test_world_provider_returns_none_when_no_file(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    _registry.clear()

    import huaqi_src.reports.providers.world

    from huaqi_src.reports.providers import get_providers
    import datetime
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)

    providers = get_providers("morning")
    ctx = providers[0].get_context("morning", date_range)
    assert ctx is None
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_providers.py::test_world_provider_returns_context -v
```

预期：`ModuleNotFoundError: No module named 'huaqi_src.reports.providers.world'`

**Step 3: 实现 WorldProvider**

注意：`WorldProvider` 需要知道 `data_dir`。设计上，Provider 在实例化时接收 `data_dir`，在 `world.py` 末尾用 `require_data_dir()` 自注册（生产用），测试时手动实例化并注册。

```python
# huaqi_src/reports/providers/world.py
import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class WorldProvider(DataProvider):
    name = "world"
    priority = 10
    supported_reports = ["morning", "daily"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        world_dir = self._data_dir / "world"
        if not world_dir.exists():
            return None
        today = date_range.end.isoformat()
        world_file = world_dir / f"{today}.md"
        if not world_file.exists():
            return None
        content = world_file.read_text(encoding="utf-8")[:1000]
        return f"## 今日世界热点\n{content}"


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(WorldProvider(_data_dir))
except Exception:
    pass
```

**Step 4: 修改测试，使用 `data_dir` 参数传入**

测试中需要手动注册带 `tmp_path` 的实例，而不是依赖模块级自注册（因为 `tmp_path` 只在测试运行时才有）。将测试改为：

```python
def test_world_provider_returns_context(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.world import WorldProvider
    _registry.clear()

    import datetime
    today = datetime.date.today()
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / f"{today.isoformat()}.md").write_text("AI 技术突破", encoding="utf-8")

    register(WorldProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    providers = get_providers("morning")
    assert len(providers) == 1

    date_range = DateRange(start=today, end=today)
    ctx = providers[0].get_context("morning", date_range)
    assert ctx is not None
    assert "AI 技术突破" in ctx


def test_world_provider_returns_none_when_no_file(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.world import WorldProvider
    _registry.clear()

    register(WorldProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    import datetime
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)

    providers = get_providers("morning")
    ctx = providers[0].get_context("morning", date_range)
    assert ctx is None
```

**Step 5: 运行测试，确认通过**

```
pytest tests/reports/test_providers.py -v
```

预期：6 tests passed

**Step 6: 提交**

```
git add huaqi_src/reports/providers/world.py tests/reports/test_providers.py
git commit -m "feat: add WorldProvider"
```

---

## Task 3: 实现 DiaryProvider

**Files:**
- Create: `huaqi_src/reports/providers/diary.py`
- Modify: `tests/reports/test_providers.py`（追加测试）

**背景：** 日记存储在 `data_dir/memory/diary/YYYY-MM-DD.md`。适用所有报告类型，优先级 20。日报取当天，周报取最近 7 天，晨报/季报取最近 3 篇。

**Step 1: 追加失败测试**

```python
def test_diary_provider_daily_returns_today(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.diary import DiaryProvider
    _registry.clear()

    import datetime
    today = datetime.date.today()
    diary_dir = tmp_path / "memory" / "diary"
    diary_dir.mkdir(parents=True)
    (diary_dir / f"{today.isoformat()}.md").write_text("今天很充实", encoding="utf-8")

    register(DiaryProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    providers = get_providers("daily")
    assert len(providers) == 1

    date_range = DateRange(start=today, end=today)
    ctx = providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "今天很充实" in ctx


def test_diary_provider_weekly_returns_multiple_days(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.diary import DiaryProvider
    import datetime
    _registry.clear()

    diary_dir = tmp_path / "memory" / "diary"
    diary_dir.mkdir(parents=True)
    today = datetime.date.today()
    for i in range(3):
        d = today - datetime.timedelta(days=i)
        (diary_dir / f"{d.isoformat()}.md").write_text(f"第{i}天日记", encoding="utf-8")

    register(DiaryProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    providers = get_providers("weekly")
    date_range = DateRange(start=today - datetime.timedelta(days=6), end=today)
    ctx = providers[0].get_context("weekly", date_range)
    assert ctx is not None
    assert "第0天日记" in ctx
    assert "第2天日记" in ctx
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_providers.py::test_diary_provider_daily_returns_today -v
```

预期：`ModuleNotFoundError`

**Step 3: 实现 DiaryProvider**

```python
# huaqi_src/reports/providers/diary.py
import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class DiaryProvider(DataProvider):
    name = "diary"
    priority = 20
    supported_reports = ["*"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        diary_dir = self._data_dir / "memory" / "diary"
        if not diary_dir.exists():
            return None

        if report_type == "daily":
            diary_file = diary_dir / f"{date_range.end.isoformat()}.md"
            if not diary_file.exists():
                return None
            content = diary_file.read_text(encoding="utf-8")[:800]
            return f"## 今日日记\n{content}"

        snippets = []
        current = date_range.end
        while current >= date_range.start:
            f = diary_dir / f"{current.isoformat()}.md"
            if f.exists():
                snippets.append(f"### {current.isoformat()}\n{f.read_text(encoding='utf-8')[:300]}")
            current -= datetime.timedelta(days=1)
            if len(snippets) >= 7:
                break

        if not snippets:
            return None
        label = "近期日记片段" if report_type == "morning" else "本周日记片段"
        return f"## {label}\n" + "\n\n".join(snippets)


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(DiaryProvider(_data_dir))
except Exception:
    pass
```

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_providers.py -v
```

预期：8 tests passed

**Step 5: 提交**

```
git add huaqi_src/reports/providers/diary.py tests/reports/test_providers.py
git commit -m "feat: add DiaryProvider"
```

---

## Task 4: 实现 PeopleProvider

**Files:**
- Create: `huaqi_src/reports/providers/people.py`
- Modify: `tests/reports/test_providers.py`（追加测试）

**背景：** 人际关系存储在 `data_dir/people/*.md`，通过 `PeopleGraph(data_dir)` 读取。适用所有报告，优先级 40。

**Step 1: 追加失败测试**

```python
def test_people_provider_returns_active_people(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.people import PeopleProvider
    from huaqi_src.people.graph import PeopleGraph
    from huaqi_src.people.models import Person
    import datetime
    _registry.clear()

    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="p1",
        name="张三",
        relation_type="同事",
        interaction_frequency=8,
    ))

    register(PeopleProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    ctx = providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "张三" in ctx


def test_people_provider_returns_none_when_empty(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.people import PeopleProvider
    import datetime
    _registry.clear()

    register(PeopleProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    ctx = providers[0].get_context("daily", date_range)
    assert ctx is None
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_providers.py::test_people_provider_returns_active_people -v
```

预期：`ModuleNotFoundError`

**Step 3: 实现 PeopleProvider**

```python
# huaqi_src/reports/providers/people.py
from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class PeopleProvider(DataProvider):
    name = "people"
    priority = 40
    supported_reports = ["*"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        people_dir = self._data_dir / "people"
        if not people_dir.exists():
            return None

        from huaqi_src.people.graph import PeopleGraph
        graph = PeopleGraph(data_dir=self._data_dir)
        people = graph.list_people()
        if not people:
            return None

        active = [p for p in people if p.interaction_frequency > 0]
        if not active:
            active = people

        active.sort(key=lambda p: p.interaction_frequency, reverse=True)

        if report_type in ("morning",):
            limit = 3
            label = "近期活跃关系人"
            lines = [f"## {label}"]
            for p in active[:limit]:
                line = f"- {p.name}（{p.relation_type}）"
                if p.notes:
                    line += f"：{p.notes}"
                lines.append(line)
        elif report_type in ("daily",):
            limit = 5
            lines = ["## 关系网络动态"]
            for p in active[:limit]:
                lines.append(f"- {p.name}（{p.relation_type}）：近30天互动 {p.interaction_frequency} 次")
        elif report_type in ("weekly",):
            limit = 8
            lines = ["## 关系人概览"]
            for p in active[:limit]:
                line = f"- {p.name}（{p.relation_type}）"
                if p.profile:
                    line += f"：{p.profile[:50]}"
                lines.append(line)
        else:
            lines = ["## 关系人全貌"]
            for p in sorted(people, key=lambda x: x.interaction_frequency, reverse=True):
                line = f"- {p.name}（{p.relation_type}，{p.emotional_impact}影响）"
                if p.profile:
                    line += f"：{p.profile[:80]}"
                lines.append(line)

        return "\n".join(lines)


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(PeopleProvider(_data_dir))
except Exception:
    pass
```

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_providers.py -v
```

预期：10 tests passed

**Step 5: 提交**

```
git add huaqi_src/reports/providers/people.py tests/reports/test_providers.py
git commit -m "feat: add PeopleProvider"
```

---

## Task 5: 实现 LearningProvider

**Files:**
- Create: `huaqi_src/reports/providers/learning.py`
- Modify: `tests/reports/test_providers.py`（追加测试）

**背景：** 学习数据通过 `LearningProgressStore(base_dir)` 读取，`base_dir` 是 `data_dir/learning`。
- `store.list_courses()` 返回所有 `CourseOutline`
- `sessions/` 目录下有 `YYYYMMDD_slug.md` 文件

优先级 30，适用 `daily`, `weekly`, `quarterly`。

**Step 1: 追加失败测试**

```python
def test_learning_provider_lists_courses(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.learning import LearningProvider
    from huaqi_src.learning.progress_store import LearningProgressStore
    from huaqi_src.learning.models import CourseOutline, LessonOutline
    import datetime
    _registry.clear()

    store = LearningProgressStore(base_dir=tmp_path / "learning")
    course = CourseOutline(
        skill_name="Rust",
        slug="rust",
        lessons=[
            LessonOutline(index=1, title="所有权", status="completed"),
            LessonOutline(index=2, title="借用", status="pending"),
        ],
    )
    store.save_course(course)

    register(LearningProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    learning_providers = [p for p in providers if p.name == "learning"]
    assert len(learning_providers) == 1

    ctx = learning_providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "Rust" in ctx
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_providers.py::test_learning_provider_lists_courses -v
```

预期：`ModuleNotFoundError`

**Step 3: 实现 LearningProvider**

```python
# huaqi_src/reports/providers/learning.py
import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class LearningProvider(DataProvider):
    name = "learning"
    priority = 30
    supported_reports = ["daily", "weekly", "quarterly"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        learning_dir = self._data_dir / "learning"
        if not learning_dir.exists():
            return None

        from huaqi_src.learning.progress_store import LearningProgressStore
        store = LearningProgressStore(base_dir=learning_dir)
        courses = store.list_courses()
        if not courses:
            return None

        lines = ["## 学习进度"]
        for course in courses:
            completed = sum(1 for l in course.lessons if l.status == "completed")
            total = course.total_lessons
            current_lesson = next(
                (l for l in course.lessons if l.index == course.current_lesson), None
            )
            current_title = current_lesson.title if current_lesson else "—"
            lines.append(
                f"- **{course.skill_name}**：{completed}/{total} 章完成，当前：{current_title}"
            )

        sessions_dir = learning_dir / "sessions"
        if sessions_dir.exists() and report_type in ("daily", "weekly"):
            recent_sessions = []
            current = date_range.end
            while current >= date_range.start:
                date_str = current.strftime("%Y%m%d")
                for f in sessions_dir.glob(f"{date_str}_*.md"):
                    recent_sessions.append(f.read_text(encoding="utf-8")[:200])
                current -= datetime.timedelta(days=1)
            if recent_sessions:
                lines.append("\n## 近期学习记录")
                lines.extend(recent_sessions[:3])

        return "\n".join(lines)


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(LearningProvider(_data_dir))
except Exception:
    pass
```

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_providers.py -v
```

预期：11 tests passed

**Step 5: 提交**

```
git add huaqi_src/reports/providers/learning.py tests/reports/test_providers.py
git commit -m "feat: add LearningProvider"
```

---

## Task 6: 实现 GrowthProvider

**Files:**
- Create: `huaqi_src/reports/providers/growth.py`
- Modify: `tests/reports/test_providers.py`（追加测试）

**背景：** 成长目标存储在 `data_dir/memory/growth.yaml`。适用 `weekly`, `quarterly`，优先级 50。

`growth.yaml` 格式示例：
```yaml
goals:
  - title: "学会 Rust"
    status: in_progress
    progress: 40%
  - title: "坚持每天写日记"
    status: active
skills:
  - name: "Python"
    level: "advanced"
  - name: "Rust"
    level: "beginner"
```

**Step 1: 追加失败测试**

```python
def test_growth_provider_returns_goals(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.growth import GrowthProvider
    import datetime
    import yaml
    _registry.clear()

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    growth_data = {
        "goals": [{"title": "学会 Rust", "status": "in_progress", "progress": "40%"}],
        "skills": [{"name": "Python", "level": "advanced"}],
    }
    (memory_dir / "growth.yaml").write_text(
        yaml.dump(growth_data, allow_unicode=True), encoding="utf-8"
    )

    register(GrowthProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("weekly")
    growth_providers = [p for p in providers if p.name == "growth"]
    assert len(growth_providers) == 1

    ctx = growth_providers[0].get_context("weekly", date_range)
    assert ctx is not None
    assert "Rust" in ctx


def test_growth_provider_not_for_daily(tmp_path):
    from huaqi_src.reports.providers import _registry
    from huaqi_src.reports.providers.growth import GrowthProvider
    _registry.clear()

    register(GrowthProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    providers = get_providers("daily")
    growth_providers = [p for p in providers if p.name == "growth"]
    assert len(growth_providers) == 0
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_providers.py::test_growth_provider_returns_goals -v
```

预期：`ModuleNotFoundError`

**Step 3: 实现 GrowthProvider**

```python
# huaqi_src/reports/providers/growth.py
from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class GrowthProvider(DataProvider):
    name = "growth"
    priority = 50
    supported_reports = ["weekly", "quarterly"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        growth_file = self._data_dir / "memory" / "growth.yaml"
        if not growth_file.exists():
            return None

        import yaml
        with open(growth_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return None

        lines = ["## 成长目标与技能"]
        goals = data.get("goals", [])
        if goals:
            lines.append("### 目标")
            for g in goals:
                title = g.get("title", "")
                status = g.get("status", "")
                progress = g.get("progress", "")
                line = f"- {title}（{status}）"
                if progress:
                    line += f" {progress}"
                lines.append(line)

        skills = data.get("skills", [])
        if skills:
            lines.append("### 技能")
            for s in skills:
                lines.append(f"- {s.get('name', '')}：{s.get('level', '')}")

        return "\n".join(lines)


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(GrowthProvider(_data_dir))
except Exception:
    pass
```

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_providers.py -v
```

预期：13 tests passed

**Step 5: 提交**

```
git add huaqi_src/reports/providers/growth.py tests/reports/test_providers.py
git commit -m "feat: add GrowthProvider"
```

---

## Task 7: 实现 EventsProvider

**Files:**
- Create: `huaqi_src/reports/providers/events.py`
- Modify: `tests/reports/test_providers.py`（追加测试）

**背景：** 事件流存储在 `data_dir/events.db`（SQLite）。需检查该数据库实际 schema。

**Step 1: 先查看 events.db 的 schema**

```
sqlite3 ~/.huaqi_data/events.db ".schema"
```

或者搜索项目中创建 events.db 的代码：

```
grep -r "events.db\|CREATE TABLE" huaqi_src/ --include="*.py" -l
```

然后读取相关文件，确认表名和字段。

**Step 2: 追加失败测试**

```python
def test_events_provider_returns_recent_events(tmp_path):
    import sqlite3
    import datetime
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.events import EventsProvider
    _registry.clear()

    db_path = tmp_path / "events.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE events (id TEXT, type TEXT, content TEXT, created_at TEXT)"
    )
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?)",
        ("e1", "chat", "完成了 Rust 第一章学习", datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    register(EventsProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    events_providers = [p for p in providers if p.name == "events"]
    assert len(events_providers) == 1

    ctx = events_providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "Rust" in ctx


def test_events_provider_returns_none_when_no_db(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.events import EventsProvider
    import datetime
    _registry.clear()

    register(EventsProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    ctx = providers[0].get_context("daily", date_range) if providers else None
    assert ctx is None
```

**注意：** 测试中建表的 SQL 可能需要根据真实 schema 调整。先运行 Step 1 确认 schema 再写测试。

**Step 3: 运行测试，确认失败**

```
pytest tests/reports/test_providers.py::test_events_provider_returns_recent_events -v
```

预期：`ModuleNotFoundError`

**Step 4: 实现 EventsProvider**

```python
# huaqi_src/reports/providers/events.py
import sqlite3
from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class EventsProvider(DataProvider):
    name = "events"
    priority = 60
    supported_reports = ["daily", "weekly"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        db_path = self._data_dir / "events.db"
        if not db_path.exists():
            return None

        try:
            conn = sqlite3.connect(str(db_path))
            start_str = date_range.start.isoformat()
            end_str = date_range.end.isoformat() + "T23:59:59"
            rows = conn.execute(
                "SELECT type, content, created_at FROM events "
                "WHERE created_at >= ? AND created_at <= ? "
                "ORDER BY created_at DESC LIMIT 20",
                (start_str, end_str),
            ).fetchall()
            conn.close()
        except Exception:
            return None

        if not rows:
            return None

        lines = ["## 近期事件流"]
        for row in rows:
            event_type, content, created_at = row
            date_part = created_at[:10] if created_at else ""
            lines.append(f"- [{date_part}] {event_type}：{content[:100]}")

        return "\n".join(lines)


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(EventsProvider(_data_dir))
except Exception:
    pass
```

**⚠️ 注意：** SQL 查询中的列名（`type`, `content`, `created_at`）需要根据 Step 1 查到的真实 schema 调整。

**Step 5: 运行测试，确认通过**

```
pytest tests/reports/test_providers.py -v
```

预期：15 tests passed

**Step 6: 提交**

```
git add huaqi_src/reports/providers/events.py tests/reports/test_providers.py
git commit -m "feat: add EventsProvider"
```

---

## Task 8: 实现 WeeklyReportProvider（供季报使用）

**Files:**
- Create: `huaqi_src/reports/providers/weekly_reports.py`
- Modify: `tests/reports/test_providers.py`（追加测试）

**背景：** 季报需要读取过去 13 周的周报文件（`data_dir/reports/weekly/*.md`）。优先级 70，只适用 `quarterly`。

**Step 1: 追加失败测试**

```python
def test_weekly_reports_provider_for_quarterly(tmp_path):
    from huaqi_src.reports.providers import _registry, DateRange
    from huaqi_src.reports.providers.weekly_reports import WeeklyReportsProvider
    import datetime
    _registry.clear()

    weekly_dir = tmp_path / "reports" / "weekly"
    weekly_dir.mkdir(parents=True)
    (weekly_dir / "2026-W12.md").write_text("# 周报 2026-W12\n本周学了 Rust 第二章", encoding="utf-8")

    register(WeeklyReportsProvider(data_dir=tmp_path))

    from huaqi_src.reports.providers import get_providers
    today = datetime.date.today()
    date_range = DateRange(start=today - datetime.timedelta(weeks=13), end=today)
    providers = get_providers("quarterly")
    assert len(providers) == 1

    ctx = providers[0].get_context("quarterly", date_range)
    assert ctx is not None
    assert "2026-W12" in ctx
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_providers.py::test_weekly_reports_provider_for_quarterly -v
```

**Step 3: 实现 WeeklyReportsProvider**

```python
# huaqi_src/reports/providers/weekly_reports.py
from pathlib import Path
from typing import Optional

from huaqi_src.reports.providers import DataProvider, DateRange, register


class WeeklyReportsProvider(DataProvider):
    name = "weekly_reports"
    priority = 70
    supported_reports = ["quarterly"]

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

    def get_context(self, report_type: str, date_range: DateRange) -> str | None:
        weekly_dir = self._data_dir / "reports" / "weekly"
        if not weekly_dir.exists():
            return None

        weekly_files = sorted(weekly_dir.glob("*.md"), reverse=True)[:13]
        if not weekly_files:
            return None

        snippets = []
        for f in weekly_files:
            snippets.append(f"### {f.stem}\n{f.read_text(encoding='utf-8')[:200]}")

        return "## 本季度周报摘要\n" + "\n\n".join(snippets)


try:
    from huaqi_src.core.config_paths import get_data_dir
    _data_dir = get_data_dir()
    if _data_dir is not None:
        register(WeeklyReportsProvider(_data_dir))
except Exception:
    pass
```

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_providers.py -v
```

预期：16 tests passed

**Step 5: 提交**

```
git add huaqi_src/reports/providers/weekly_reports.py tests/reports/test_providers.py
git commit -m "feat: add WeeklyReportsProvider"
```

---

## Task 9: 实现 ContextBuilder

**Files:**
- Create: `huaqi_src/reports/context_builder.py`
- Create: `tests/reports/test_context_builder.py`

**Step 1: 写失败测试**

```python
# tests/reports/test_context_builder.py
import datetime
from pathlib import Path
from huaqi_src.reports.providers import _registry, DateRange


def test_build_context_combines_providers(tmp_path):
    _registry.clear()

    from huaqi_src.reports.providers import register, DataProvider

    class FakeProvider1(DataProvider):
        name = "fake1"
        priority = 10
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return "数据A"

    class FakeProvider2(DataProvider):
        name = "fake2"
        priority = 20
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return "数据B"

    register(FakeProvider1())
    register(FakeProvider2())

    from huaqi_src.reports.context_builder import build_context
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    result = build_context("daily", date_range)
    assert "数据A" in result
    assert "数据B" in result


def test_build_context_skips_none_providers(tmp_path):
    _registry.clear()

    from huaqi_src.reports.providers import register, DataProvider

    class EmptyProvider(DataProvider):
        name = "empty"
        priority = 10
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return None

    class RealProvider(DataProvider):
        name = "real"
        priority = 20
        supported_reports = ["daily"]

        def get_context(self, report_type, date_range):
            return "真实数据"

    register(EmptyProvider())
    register(RealProvider())

    from huaqi_src.reports.context_builder import build_context
    import datetime
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    result = build_context("daily", date_range)
    assert "真实数据" in result
    assert result.count("\n\n") == 0


def test_build_context_returns_fallback_when_all_none():
    _registry.clear()

    from huaqi_src.reports.context_builder import build_context
    from huaqi_src.reports.providers import DateRange
    import datetime
    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    result = build_context("daily", date_range)
    assert result == "暂无上下文数据。"
```

**Step 2: 运行测试，确认失败**

```
pytest tests/reports/test_context_builder.py -v
```

预期：`ModuleNotFoundError`

**Step 3: 实现 ContextBuilder**

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

**Step 4: 运行测试，确认通过**

```
pytest tests/reports/test_context_builder.py -v
```

预期：3 tests passed

**Step 5: 提交**

```
git add huaqi_src/reports/context_builder.py tests/reports/test_context_builder.py
git commit -m "feat: add context_builder"
```

---

## Task 10: 重构报告类使用 ContextBuilder

**Files:**
- Modify: `huaqi_src/reports/morning_brief.py`
- Modify: `huaqi_src/reports/daily_report.py`
- Modify: `huaqi_src/reports/weekly_report.py`
- Modify: `huaqi_src/reports/quarterly_report.py`
- Test: `tests/reports/test_morning_brief.py`（已有，确认仍通过）

**Step 1: 阅读现有 4 个报告类的 `_build_context()` 方法**

已在上方背景中提供，主要变化：
- `MorningBriefAgent._build_context()` → 调用 `build_context("morning", date_range)`
- `DailyReportAgent._build_context()` → 调用 `build_context("daily", date_range)`
- `WeeklyReportAgent._build_context()` → 调用 `build_context("weekly", date_range)`
- `QuarterlyReportAgent._build_context()` → 调用 `build_context("quarterly", date_range)`

**Step 2: 重构 MorningBriefAgent**

将 `morning_brief.py` 的 `_build_context()` 替换为：

```python
def _build_context(self) -> str:
    import datetime
    from huaqi_src.reports.providers import DateRange
    from huaqi_src.reports.context_builder import build_context
    from huaqi_src.reports import providers  # noqa: F401 触发 providers 包加载

    import huaqi_src.reports.providers.world
    import huaqi_src.reports.providers.diary
    import huaqi_src.reports.providers.people

    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    return build_context("morning", date_range)
```

**注意：** 由于 Provider 实例化时需要 `data_dir`，而报告类的 `self._data_dir` 才是正确的路径，需要在调用前将 Provider 手动注册（带 `data_dir`），而非依赖模块级自注册。

推荐做法：在 `__init__` 中完成注册，而非在 `_build_context` 中重复注册。修改方案如下：

```python
# huaqi_src/reports/morning_brief.py
import datetime
from pathlib import Path
from typing import Optional


class MorningBriefAgent:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.core.config_paths import require_data_dir
            self._data_dir = require_data_dir()

        self._register_providers()

    def _register_providers(self) -> None:
        from huaqi_src.reports.providers import _registry
        from huaqi_src.reports.providers.world import WorldProvider
        from huaqi_src.reports.providers.diary import DiaryProvider
        from huaqi_src.reports.providers.people import PeopleProvider

        for p in list(_registry):
            if p.name in ("world", "diary", "people"):
                _registry.remove(p)

        from huaqi_src.reports.providers import register
        register(WorldProvider(self._data_dir))
        register(DiaryProvider(self._data_dir))
        register(PeopleProvider(self._data_dir))

    def _build_context(self) -> str:
        from huaqi_src.reports.providers import DateRange
        from huaqi_src.reports.context_builder import build_context
        today = datetime.date.today()
        date_range = DateRange(start=today, end=today)
        return build_context("morning", date_range)

    def _generate_brief(self) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage
        context = self._build_context()
        from huaqi_src.cli.context import build_llm_manager
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=500)
        if llm_mgr is None:
            return "（LLM 未配置，无法生成简报）"
        active_name = llm_mgr.get_active_provider()
        if not active_name:
            return "（未配置任何 LLM 提供商）"
        cfg = llm_mgr._configs[active_name]
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.7,
            max_tokens=500,
        )
        system_prompt = (
            "你是 huaqi，用户的 AI 同伴。请根据以下背景信息，生成一份简洁温暖的晨间简报，"
            "包含：1）今日世界热点摘要（如有），2）对用户近期状态的简短观察，3）一句鼓励的话。"
            "简报应简短，不超过 300 字。"
        )
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"背景信息：\n{context}"),
        ])
        return response.content

    def run(self) -> str:
        brief = self._generate_brief()
        report_dir = self._data_dir / "reports" / "daily"
        report_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        report_file = report_dir / f"{today}-morning.md"
        report_file.write_text(f"# 晨间简报 {today}\n\n{brief}\n", encoding="utf-8")
        return brief
```

**Step 3: 类似重构 DailyReportAgent**

`_register_providers` 中注册：`WorldProvider`, `DiaryProvider`, `PeopleProvider`
（支持 `"daily"` 的那些）

**Step 4: 类似重构 WeeklyReportAgent**

`_register_providers` 中注册：`DiaryProvider`, `PeopleProvider`, `LearningProvider`, `GrowthProvider`

**Step 5: 类似重构 QuarterlyReportAgent**

`_register_providers` 中注册：`PeopleProvider`, `GrowthProvider`, `WeeklyReportsProvider`, `LearningProvider`

**Step 6: 运行所有报告测试，确认通过**

```
pytest tests/reports/ -v
```

预期：原有测试全部通过（已有测试不测试 `_build_context()` 内部细节，只测文件创建和 context 包含特定字段）

**Step 7: 提交**

```
git add huaqi_src/reports/
git commit -m "refactor: reports use context_builder via DataProvider registry"
```

---

## Task 11: 全量测试通过

**Step 1: 运行所有测试**

```
pytest tests/ -v
```

预期：所有测试通过，无失败。

**Step 2: 如有失败，逐一修复**

常见问题：
- `_registry` 在多个测试间未清空 → 在测试函数开头加 `_registry.clear()`
- Provider 自注册在 `data_dir=None` 时失败 → 检查 `try/except` 是否正确捕获

**Step 3: 最终提交**

```
git add -A
git commit -m "test: all provider and report tests passing"
```

---

## 扩展指南（新增数据模块时）

后续新增数据模块（如 `work_docs`、`inbox`）接入报告系统，只需 5 步：

1. 在 `huaqi_src/reports/providers/` 下新建文件（如 `work_docs.py`）
2. 实现 `DataProvider` 子类，设置 `name`, `priority`, `supported_reports`
3. 实现 `get_context()` 方法，返回 `str | None`
4. 文件末尾加自注册代码（`try/except` 保护）
5. 在对应报告类的 `_register_providers()` 中添加一行 import + register

无需修改任何报告文件的 LLM Prompt 或 `run()` 方法。
