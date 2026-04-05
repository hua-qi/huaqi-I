import datetime
from datetime import date
from pathlib import Path
from huaqi_src.layers.capabilities.reports.providers import DataProvider, DateRange, register, get_providers, _registry


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


def test_world_provider_returns_context(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
    _registry.clear()

    today = datetime.date.today()
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / f"{today.isoformat()}.md").write_text("AI 技术突破", encoding="utf-8")

    register(WorldProvider(data_dir=tmp_path))

    providers = get_providers("morning")
    assert len(providers) == 1

    date_range = DateRange(start=today, end=today)
    ctx = providers[0].get_context("morning", date_range)
    assert ctx is not None
    assert "AI 技术突破" in ctx


def test_world_provider_returns_none_when_no_file(tmp_path):
    from unittest.mock import patch
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
    _registry.clear()

    register(WorldProvider(data_dir=tmp_path))

    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)

    with patch.object(WorldProvider, "_lazy_fetch", return_value=None):
        providers = get_providers("morning")
        ctx = providers[0].get_context("morning", date_range)
    assert ctx is None


def test_diary_provider_daily_returns_today(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.diary import DiaryProvider
    _registry.clear()

    today = datetime.date.today()
    diary_dir = tmp_path / "memory" / "diary"
    diary_dir.mkdir(parents=True)
    (diary_dir / f"{today.isoformat()}.md").write_text("今天很充实", encoding="utf-8")

    register(DiaryProvider(data_dir=tmp_path))

    providers = get_providers("daily")
    assert len(providers) == 1

    date_range = DateRange(start=today, end=today)
    ctx = providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "今天很充实" in ctx


def test_diary_provider_weekly_returns_multiple_days(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.diary import DiaryProvider
    _registry.clear()

    diary_dir = tmp_path / "memory" / "diary"
    diary_dir.mkdir(parents=True)
    today = datetime.date.today()
    for i in range(3):
        d = today - datetime.timedelta(days=i)
        (diary_dir / f"{d.isoformat()}.md").write_text(f"第{i}天日记", encoding="utf-8")

    register(DiaryProvider(data_dir=tmp_path))

    providers = get_providers("weekly")
    date_range = DateRange(start=today - datetime.timedelta(days=6), end=today)
    ctx = providers[0].get_context("weekly", date_range)
    assert ctx is not None
    assert "第0天日记" in ctx
    assert "第2天日记" in ctx


def test_people_provider_returns_active_people(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.people import PeopleProvider
    from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph
    from huaqi_src.layers.growth.telos.dimensions.people.models import Person
    _registry.clear()

    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="p1",
        name="张三",
        relation_type="同事",
        interaction_frequency=8,
    ))

    register(PeopleProvider(data_dir=tmp_path))

    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    ctx = providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "张三" in ctx


def test_people_provider_returns_none_when_empty(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.people import PeopleProvider
    _registry.clear()

    register(PeopleProvider(data_dir=tmp_path))

    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    ctx = providers[0].get_context("daily", date_range)
    assert ctx is None


def test_learning_provider_lists_courses(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.learning import LearningProvider
    from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore
    from huaqi_src.layers.capabilities.learning.models import CourseOutline, LessonOutline
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

    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    learning_providers = [p for p in providers if p.name == "learning"]
    assert len(learning_providers) == 1

    ctx = learning_providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "Rust" in ctx


def test_growth_provider_returns_goals(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.growth import GrowthProvider
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

    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("weekly")
    growth_providers = [p for p in providers if p.name == "growth"]
    assert len(growth_providers) == 1

    ctx = growth_providers[0].get_context("weekly", date_range)
    assert ctx is not None
    assert "Rust" in ctx


def test_growth_provider_not_for_daily(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry
    from huaqi_src.layers.capabilities.reports.providers.growth import GrowthProvider
    _registry.clear()

    register(GrowthProvider(data_dir=tmp_path))

    providers = get_providers("daily")
    growth_providers = [p for p in providers if p.name == "growth"]
    assert len(growth_providers) == 0


def test_events_provider_returns_recent_events(tmp_path):
    import sqlite3
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.events import EventsProvider
    _registry.clear()

    db_path = tmp_path / "events.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, source TEXT, actor TEXT, content TEXT, context_id TEXT)"
    )
    import time
    conn.execute(
        "INSERT INTO events (timestamp, source, actor, content, context_id) VALUES (?, ?, ?, ?, ?)",
        (int(time.time()), "chat", "user", "完成了 Rust 第一章学习", None),
    )
    conn.commit()
    conn.close()

    register(EventsProvider(data_dir=tmp_path))

    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    events_providers = [p for p in providers if p.name == "events"]
    assert len(events_providers) == 1

    ctx = events_providers[0].get_context("daily", date_range)
    assert ctx is not None
    assert "Rust" in ctx


def test_events_provider_returns_none_when_no_db(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.events import EventsProvider
    _registry.clear()

    register(EventsProvider(data_dir=tmp_path))

    today = datetime.date.today()
    date_range = DateRange(start=today, end=today)
    providers = get_providers("daily")
    events_providers = [p for p in providers if p.name == "events"]
    ctx = events_providers[0].get_context("daily", date_range) if events_providers else None
    assert ctx is None


def test_weekly_reports_provider_for_quarterly(tmp_path):
    from huaqi_src.layers.capabilities.reports.providers import _registry, DateRange
    from huaqi_src.layers.capabilities.reports.providers.weekly_reports import WeeklyReportsProvider
    _registry.clear()

    weekly_dir = tmp_path / "reports" / "weekly"
    weekly_dir.mkdir(parents=True)
    (weekly_dir / "2026-W12.md").write_text("# 周报 2026-W12\n本周学了 Rust 第二章", encoding="utf-8")

    register(WeeklyReportsProvider(data_dir=tmp_path))

    today = datetime.date.today()
    date_range = DateRange(start=today - datetime.timedelta(weeks=13), end=today)
    providers = get_providers("quarterly")
    assert len(providers) == 1

    ctx = providers[0].get_context("quarterly", date_range)
    assert ctx is not None
    assert "2026-W12" in ctx
