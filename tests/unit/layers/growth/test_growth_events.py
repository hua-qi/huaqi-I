import pytest
from datetime import datetime, timezone
from pathlib import Path

from huaqi_src.layers.growth.telos.growth_events import GrowthEventStore, GrowthEvent
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter


@pytest.fixture
def event_store(tmp_path: Path) -> GrowthEventStore:
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    return GrowthEventStore(adapter=adapter)


@pytest.fixture
def sample_event() -> GrowthEvent:
    return GrowthEvent(
        user_id="user_a",
        dimension="beliefs",
        layer="core",
        title="开始相信选择的力量",
        narrative="你开始相信选择比努力更重要了。这个转变不是一夜之间发生的。",
        old_content="努力一定有回报",
        new_content="选择比努力更重要",
        trigger_signals=["signal-uuid-1", "signal-uuid-2"],
        occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
    )


class TestGrowthEventModel:
    def test_id_auto_generated(self, sample_event):
        assert sample_event.id is not None
        assert len(sample_event.id) == 36

    def test_narrative_not_empty(self):
        with pytest.raises(Exception):
            GrowthEvent(
                user_id="user_a",
                dimension="beliefs",
                layer="core",
                title="标题",
                narrative="",
                new_content="新内容",
                trigger_signals=[],
                occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
            )

    def test_title_not_empty(self):
        with pytest.raises(Exception):
            GrowthEvent(
                user_id="user_a",
                dimension="beliefs",
                layer="core",
                title="",
                narrative="叙事",
                new_content="新内容",
                trigger_signals=[],
                occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
            )


class TestGrowthEventStore:
    def test_save_and_get(self, event_store, sample_event):
        event_store.save(sample_event)
        result = event_store.get(sample_event.id)
        assert result is not None
        assert result.id == sample_event.id
        assert result.title == sample_event.title

    def test_get_nonexistent_returns_none(self, event_store):
        assert event_store.get("nonexistent-id") is None

    def test_narrative_preserved(self, event_store, sample_event):
        event_store.save(sample_event)
        result = event_store.get(sample_event.id)
        assert result.narrative == sample_event.narrative

    def test_trigger_signals_preserved(self, event_store, sample_event):
        event_store.save(sample_event)
        result = event_store.get(sample_event.id)
        assert result.trigger_signals == sample_event.trigger_signals

    def test_old_content_can_be_none(self, event_store):
        event = GrowthEvent(
            user_id="user_a",
            dimension="beliefs",
            layer="core",
            title="首次认知",
            narrative="第一次形成这个信念。",
            old_content=None,
            new_content="选择比努力更重要",
            trigger_signals=[],
            occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        event_store.save(event)
        result = event_store.get(event.id)
        assert result.old_content is None


class TestGrowthEventQuery:
    def test_list_by_user_sorted_by_time_desc(self, event_store):
        e1 = GrowthEvent(
            user_id="user_a", dimension="beliefs", layer="core",
            title="事件1", narrative="叙事1", new_content="内容1",
            trigger_signals=[], occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        e2 = GrowthEvent(
            user_id="user_a", dimension="goals", layer="middle",
            title="事件2", narrative="叙事2", new_content="内容2",
            trigger_signals=[], occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        event_store.save(e1)
        event_store.save(e2)

        results = event_store.list_by_user("user_a")
        assert len(results) == 2
        assert results[0].occurred_at >= results[1].occurred_at

    def test_list_by_user_isolation(self, event_store):
        ea = GrowthEvent(
            user_id="user_a", dimension="beliefs", layer="core",
            title="A的事件", narrative="叙事", new_content="内容",
            trigger_signals=[], occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        eb = GrowthEvent(
            user_id="user_b", dimension="beliefs", layer="core",
            title="B的事件", narrative="叙事", new_content="内容",
            trigger_signals=[], occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        event_store.save(ea)
        event_store.save(eb)

        results_a = event_store.list_by_user("user_a")
        assert len(results_a) == 1
        assert results_a[0].user_id == "user_a"

    def test_list_by_dimension(self, event_store):
        e1 = GrowthEvent(
            user_id="user_a", dimension="beliefs", layer="core",
            title="信念变化", narrative="叙事", new_content="内容",
            trigger_signals=[], occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        e2 = GrowthEvent(
            user_id="user_a", dimension="goals", layer="middle",
            title="目标更新", narrative="叙事", new_content="内容",
            trigger_signals=[], occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        event_store.save(e1)
        event_store.save(e2)

        results = event_store.list_by_user("user_a", dimension="beliefs")
        assert len(results) == 1
        assert results[0].dimension == "beliefs"
