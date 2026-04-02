"""
能力层测试：学习追踪

验证：
- LearningTracker 能记录学习事件（信号写入 RawSignalStore）
- 学习进度可以查询（已完成课程数/总数）
- TELOS 的 learned 维度被正确触发（Step1 识别为 learned）
- 学习记录和信号挂钩（source_type=ai_chat 或自定义 learning）
- 无学习记录时进度为 0
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
from huaqi_src.layers.capabilities.learning.tracker import (
    LearningTracker,
    LearningRecord,
    LearningProgress,
)
from huaqi_src.layers.data.raw_signal.models import RawSignalFilter, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def storage_adapter(tmp_path: Path) -> SQLiteStorageAdapter:
    return SQLiteStorageAdapter(db_path=tmp_path / "test.db")


@pytest.fixture
def signal_store(storage_adapter: SQLiteStorageAdapter) -> RawSignalStore:
    return RawSignalStore(adapter=storage_adapter)


@pytest.fixture
def tracker(signal_store: RawSignalStore) -> LearningTracker:
    return LearningTracker(signal_store=signal_store)


# ── 测试：LearningRecord 模型 ─────────────────────────────────────────────────

class TestLearningRecord:
    def test_valid_record(self):
        record = LearningRecord(
            user_id="user_a",
            topic="LangGraph 状态机设计",
            source="读书笔记",
            insight="LangGraph 用 TypedDict 传状态，节点间松耦合",
            occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        assert record.topic == "LangGraph 状态机设计"
        assert record.insight is not None

    def test_insight_optional(self):
        record = LearningRecord(
            user_id="user_a",
            topic="Python 类型注解",
            source="实践",
            occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        assert record.insight is None

    def test_empty_topic_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LearningRecord(
                user_id="user_a",
                topic="",
                source="实践",
                occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
            )


# ── 测试：LearningTracker.record ─────────────────────────────────────────────

class TestLearningTrackerRecord:
    def test_record_creates_raw_signal(self, tracker, signal_store):
        record = LearningRecord(
            user_id="user_a",
            topic="LangGraph 状态机",
            source="读书",
            insight="状态机解耦节点逻辑",
            occurred_at=datetime.now(timezone.utc),
        )
        tracker.record(record)

        signals = signal_store.query(RawSignalFilter(user_id="user_a"))
        assert len(signals) == 1
        assert "LangGraph" in signals[0].content

    def test_record_source_type_is_reading_or_chat(self, tracker, signal_store):
        record = LearningRecord(
            user_id="user_a",
            topic="Pydantic v2",
            source="文档",
            occurred_at=datetime.now(timezone.utc),
        )
        tracker.record(record)

        signals = signal_store.query(RawSignalFilter(user_id="user_a"))
        assert signals[0].source_type in (SourceType.READING, SourceType.AI_CHAT, SourceType.JOURNAL)

    def test_record_insight_in_content(self, tracker, signal_store):
        record = LearningRecord(
            user_id="user_a",
            topic="第一性原理",
            source="思考",
            insight="从基本公理出发推导，而不是类比推断",
            occurred_at=datetime.now(timezone.utc),
        )
        tracker.record(record)

        signals = signal_store.query(RawSignalFilter(user_id="user_a"))
        assert "第一性原理" in signals[0].content
        assert "基本公理" in signals[0].content

    def test_multiple_records_all_stored(self, tracker, signal_store):
        for i in range(3):
            tracker.record(LearningRecord(
                user_id="user_a",
                topic=f"主题 {i}",
                source="实践",
                occurred_at=datetime.now(timezone.utc),
            ))
        count = signal_store.count(RawSignalFilter(user_id="user_a"))
        assert count == 3


# ── 测试：LearningProgress ────────────────────────────────────────────────────

class TestLearningProgress:
    def test_progress_zero_when_no_records(self):
        p = LearningProgress(total=0, completed=0)
        assert p.completion_rate == 0.0

    def test_progress_rate_calculation(self):
        p = LearningProgress(total=10, completed=7)
        assert abs(p.completion_rate - 0.7) < 0.001

    def test_progress_full_completion(self):
        p = LearningProgress(total=5, completed=5)
        assert p.completion_rate == 1.0


# ── 测试：LearningTracker.get_progress ───────────────────────────────────────

class TestLearningTrackerProgress:
    def test_progress_empty(self, tracker):
        progress = tracker.get_progress(user_id="user_a", days=7)
        assert progress.total == 0
        assert progress.completed == 0

    def test_progress_counts_records(self, tracker):
        for i in range(4):
            tracker.record(LearningRecord(
                user_id="user_a",
                topic=f"主题 {i}",
                source="实践",
                occurred_at=datetime.now(timezone.utc),
            ))
        progress = tracker.get_progress(user_id="user_a", days=7)
        assert progress.total == 4

    def test_progress_isolates_by_user(self, tracker):
        tracker.record(LearningRecord(
            user_id="user_a",
            topic="A 的学习",
            source="实践",
            occurred_at=datetime.now(timezone.utc),
        ))
        tracker.record(LearningRecord(
            user_id="user_b",
            topic="B 的学习",
            source="实践",
            occurred_at=datetime.now(timezone.utc),
        ))
        progress_a = tracker.get_progress(user_id="user_a", days=7)
        assert progress_a.total == 1

    def test_progress_recent_topics(self, tracker):
        topics = ["LangGraph", "Pydantic", "ChromaDB"]
        for t in topics:
            tracker.record(LearningRecord(
                user_id="user_a",
                topic=t,
                source="实践",
                occurred_at=datetime.now(timezone.utc),
            ))
        progress = tracker.get_progress(user_id="user_a", days=7)
        assert set(progress.recent_topics) == set(topics)


# ── 测试：学习记录触发 TELOS learned 维度 ────────────────────────────────────

class TestLearningToTelosTrigger:
    def test_learning_signal_identified_as_learned_by_step1(self, tracker, signal_store):
        from huaqi_src.layers.growth.telos.manager import TelosManager
        from huaqi_src.layers.growth.telos.engine import TelosEngine
        import json

        record = LearningRecord(
            user_id="user_a",
            topic="LangGraph 状态机",
            source="读书",
            insight="用 TypedDict 传状态，节点间松耦合",
            occurred_at=datetime.now(timezone.utc),
        )
        tracker.record(record)

        signals = signal_store.query(RawSignalFilter(user_id="user_a"))
        assert len(signals) == 1

        mock_step1_output = {
            "dimensions": ["learned"],
            "emotion": "positive",
            "intensity": 0.7,
            "signal_strength": "medium",
            "strong_reason": None,
            "summary": "用户学习了 LangGraph 状态机设计模式",
            "new_dimension_hint": None,
        }
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(mock_step1_output))

        telos_dir = Path("/tmp/test_telos_learning")
        telos_dir.mkdir(exist_ok=True)
        telos_manager = TelosManager(telos_dir=telos_dir, git_commit=False)
        telos_manager.init()
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = engine.step1_analyze(signals[0])
        assert "learned" in result.dimensions
