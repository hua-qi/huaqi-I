import pytest
from datetime import datetime, timezone
from pathlib import Path

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter


@pytest.fixture
def store(tmp_path: Path) -> RawSignalStore:
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    return RawSignalStore(adapter=adapter)


@pytest.fixture
def signal_a() -> RawSignal:
    return RawSignal(
        user_id="user_a",
        source_type=SourceType.JOURNAL,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        content="用户 A 的日记",
    )


@pytest.fixture
def signal_b() -> RawSignal:
    return RawSignal(
        user_id="user_b",
        source_type=SourceType.JOURNAL,
        timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        content="用户 B 的日记",
    )


@pytest.fixture
def chat_signal() -> RawSignal:
    return RawSignal(
        user_id="user_a",
        source_type=SourceType.AI_CHAT,
        timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        content="和 AI 聊天记录",
    )


class TestStoreWrite:
    def test_save_and_get(self, store, signal_a):
        store.save(signal_a)
        result = store.get(signal_a.id)
        assert result is not None
        assert result.id == signal_a.id
        assert result.content == signal_a.content

    def test_get_nonexistent_returns_none(self, store):
        result = store.get("nonexistent-id")
        assert result is None

    def test_save_idempotent(self, store, signal_a):
        store.save(signal_a)
        store.save(signal_a)
        count = store.count(RawSignalFilter(user_id="user_a"))
        assert count == 1

    def test_count_after_batch_save(self, store, signal_a, chat_signal):
        store.save(signal_a)
        store.save(chat_signal)
        count = store.count(RawSignalFilter(user_id="user_a"))
        assert count == 2


class TestUserIsolation:
    def test_user_a_cannot_read_user_b(self, store, signal_a, signal_b):
        store.save(signal_a)
        store.save(signal_b)

        results_a = store.query(RawSignalFilter(user_id="user_a"))
        results_b = store.query(RawSignalFilter(user_id="user_b"))

        assert all(r.user_id == "user_a" for r in results_a)
        assert all(r.user_id == "user_b" for r in results_b)
        assert len(results_a) == 1
        assert len(results_b) == 1


class TestQuery:
    def test_query_by_source_type(self, store, signal_a, chat_signal):
        store.save(signal_a)
        store.save(chat_signal)

        results = store.query(RawSignalFilter(user_id="user_a", source_type=SourceType.JOURNAL))
        assert len(results) == 1
        assert results[0].source_type == SourceType.JOURNAL

    def test_query_unprocessed_only(self, store, signal_a, chat_signal):
        store.save(signal_a)
        store.save(chat_signal)
        store.mark_processed(signal_a.id)

        results = store.query(RawSignalFilter(user_id="user_a", processed=0))
        assert len(results) == 1
        assert results[0].id == chat_signal.id

    def test_query_by_timestamp_range(self, store):
        early = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2025, 12, 1, tzinfo=timezone.utc),
            content="早期信号",
        )
        recent = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, 4, tzinfo=timezone.utc),
            content="最近信号",
        )
        store.save(early)
        store.save(recent)

        results = store.query(RawSignalFilter(
            user_id="user_a",
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ))
        assert len(results) == 1
        assert results[0].content == "最近信号"

    def test_query_limit(self, store):
        for i in range(5):
            store.save(RawSignal(
                user_id="user_a",
                source_type=SourceType.JOURNAL,
                timestamp=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                content=f"日记 {i}",
            ))
        results = store.query(RawSignalFilter(user_id="user_a", limit=3))
        assert len(results) == 3

    def test_query_returns_sorted_by_timestamp_desc(self, store, signal_a, chat_signal):
        store.save(signal_a)
        store.save(chat_signal)

        results = store.query(RawSignalFilter(user_id="user_a"))
        assert results[0].timestamp >= results[1].timestamp


class TestStatusUpdates:
    def test_mark_processed(self, store, signal_a):
        store.save(signal_a)
        store.mark_processed(signal_a.id)

        result = store.get(signal_a.id)
        assert result.processed is True

    def test_mark_distilled(self, store, signal_a):
        store.save(signal_a)
        store.mark_distilled(signal_a.id)

        result = store.get(signal_a.id)
        assert result.distilled is True

    def test_mark_vectorized(self, store, signal_a):
        store.save(signal_a)
        store.mark_vectorized(signal_a.id)

        result = store.get(signal_a.id)
        assert result.vectorized is True

    def test_distilled_signals_excluded_from_hot_query(self, store, signal_a, chat_signal):
        store.save(signal_a)
        store.save(chat_signal)
        store.mark_distilled(signal_a.id)

        results = store.query(RawSignalFilter(user_id="user_a", distilled=0))
        assert len(results) == 1
        assert results[0].id == chat_signal.id

    def test_query_unvectorized_only(self, store, signal_a, chat_signal):
        store.save(signal_a)
        store.save(chat_signal)
        store.mark_vectorized(signal_a.id)

        results = store.query(RawSignalFilter(user_id="user_a", vectorized=0))
        assert len(results) == 1
        assert results[0].id == chat_signal.id


class TestSearchByEmbedding:
    def test_search_by_embedding_returns_top_k(self, store):
        for i in range(5):
            signal = RawSignal(
                user_id="u1",
                source_type=SourceType.JOURNAL,
                timestamp=datetime.now(timezone.utc),
                content=f"内容{i}",
                embedding=[float(i), 0.0, 0.0],
            )
            store.save(signal)

        query_vec = [4.0, 0.0, 0.0]
        results = store.search_by_embedding(user_id="u1", query_vec=query_vec, top_k=2)
        assert len(results) <= 2
        assert all(hasattr(r, "content") for r in results)

    def test_search_by_embedding_returns_empty_when_no_embeddings(self, store):
        signal = RawSignal(
            user_id="u1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="无向量内容",
        )
        store.save(signal)

        results = store.search_by_embedding(user_id="u1", query_vec=[1.0, 0.0], top_k=3)
        assert results == []
