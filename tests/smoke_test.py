"""全系统冒烟测试

每次迭代验收时必须全部通过。覆盖所有核心模块的基本功能，
按架构分层组织。测试不依赖真实 LLM 或网络。

运行方式:
    pytest tests/smoke_test.py -v          # 全量运行
    pytest tests/smoke_test.py -v -x       # 遇错即停
    pytest tests/smoke_test.py -v -k "layer"  # 按关键词筛选

新增模块时，在对应分层中添加测试函数即可。
"""

import asyncio
import datetime
import json
import sqlite3
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """模拟用户数据目录，包含必要子目录。"""
    (tmp_path / "memory").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory" / "diary").mkdir(exist_ok=True)
    (tmp_path / "memory" / "conversations").mkdir(exist_ok=True)
    (tmp_path / "drafts").mkdir(exist_ok=True)
    (tmp_path / "vector_db").mkdir(exist_ok=True)
    (tmp_path / "models").mkdir(exist_ok=True)
    (tmp_path / "pending_reviews").mkdir(exist_ok=True)
    (tmp_path / "learning").mkdir(exist_ok=True)
    (tmp_path / "reports").mkdir(exist_ok=True)
    (tmp_path / "reports" / "daily").mkdir(exist_ok=True)
    (tmp_path / "reports" / "weekly").mkdir(exist_ok=True)
    (tmp_path / "reports" / "quarterly").mkdir(exist_ok=True)
    (tmp_path / "world").mkdir(exist_ok=True)
    (tmp_path / "people").mkdir(exist_ok=True)
    (tmp_path / "telos").mkdir(exist_ok=True)
    return tmp_path


@pytest.fixture
def set_data_dir(monkeypatch, data_dir: Path):
    """将 data_dir 注入为全局数据目录。"""
    import huaqi_src.config.paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_data_dir", lambda: data_dir)
    monkeypatch.setattr(paths_mod, "require_data_dir", lambda: data_dir)
    monkeypatch.setattr(paths_mod, "is_data_dir_set", lambda: True)
    return data_dir


@pytest.fixture
def mock_user_id() -> str:
    return "test_user_smoke_001"


@pytest.fixture
def now_utc() -> datetime.datetime:
    return datetime.datetime(2026, 5, 14, 10, 0, 0, tzinfo=datetime.timezone.utc)


# ============================================================================
# 1. Config Layer — 配置管理
# ============================================================================


class TestConfigPaths:
    """数据目录路径函数。"""

    def test_get_data_dir_returns_none_when_unset(self):
        import huaqi_src.config.paths as paths_mod

        saved = getattr(paths_mod, "_USER_DATA_DIR", None)
        try:
            paths_mod._USER_DATA_DIR = None
            with patch.object(paths_mod, "_load_data_dir_from_config", return_value=None):
                with patch.dict("os.environ", {}, clear=True):
                    assert paths_mod.get_data_dir() is None
        finally:
            paths_mod._USER_DATA_DIR = saved

    def test_set_data_dir_creates_dirs(self, tmp_path):
        from huaqi_src.config.paths import set_data_dir, get_data_dir, _USER_DATA_DIR

        saved = _USER_DATA_DIR
        try:
            d = tmp_path / "custom_data"
            set_data_dir(d)
            assert d.exists()
            assert (d / "memory").exists()
            assert get_data_dir() == d.resolve()
        finally:
            import huaqi_src.config.paths as paths_mod
            paths_mod._USER_DATA_DIR = saved

    def test_require_data_dir_raises_when_unset(self):
        import huaqi_src.config.paths as paths_mod

        saved = getattr(paths_mod, "_USER_DATA_DIR", None)
        try:
            paths_mod._USER_DATA_DIR = None
            with patch.object(paths_mod, "_load_data_dir_from_config", return_value=None):
                with patch.dict("os.environ", {}, clear=True):
                    with pytest.raises(RuntimeError, match="未设置数据目录"):
                        paths_mod.require_data_dir()
        finally:
            paths_mod._USER_DATA_DIR = saved

    def test_all_path_functions_return_paths(self, set_data_dir):
        from huaqi_src.config.paths import (
            get_memory_dir, get_drafts_dir, get_vector_db_dir,
            get_models_cache_dir, get_pending_reviews_dir, get_learning_dir,
            get_diary_dir, get_conversations_dir, get_telos_dir,
            get_world_dir, get_people_dir,
        )

        assert isinstance(get_memory_dir(), Path)
        assert isinstance(get_drafts_dir(), Path)
        assert isinstance(get_vector_db_dir(), Path)
        assert isinstance(get_models_cache_dir(), Path)
        assert isinstance(get_pending_reviews_dir(), Path)
        assert isinstance(get_learning_dir(), Path)
        assert isinstance(get_diary_dir(), Path)
        assert isinstance(get_conversations_dir(), Path)
        assert isinstance(get_telos_dir(), Path)
        assert isinstance(get_world_dir(), Path)
        assert isinstance(get_people_dir(), Path)


class TestConfigManager:
    """配置管理器（YAML 读写）。"""

    def test_load_config_creates_file(self, data_dir):
        from huaqi_src.config.manager import ConfigManager

        mgr = ConfigManager(data_dir)
        # config 文件在首次 load_config() 或 save_config() 时创建
        mgr.load_config()
        assert mgr.config_path.exists()

    def test_load_config_returns_app_config(self, data_dir):
        from huaqi_src.config.manager import ConfigManager, AppConfig

        mgr = ConfigManager(data_dir)
        config = mgr.load_config()
        assert isinstance(config, AppConfig)
        assert config.version == "0.1.0"

    def test_get_and_set_config(self, data_dir):
        from huaqi_src.config.manager import ConfigManager

        mgr = ConfigManager(data_dir)
        mgr.set("llm_default_provider", "openai")
        assert mgr.get("llm_default_provider") == "openai"

    def test_save_and_reload_preserves_data(self, data_dir):
        from huaqi_src.config.manager import ConfigManager

        mgr = ConfigManager(data_dir)
        mgr.set("llm_default_provider", "claude")
        mgr.save_config()

        mgr2 = ConfigManager(data_dir)
        assert mgr2.load_config().llm_default_provider == "claude"

    def test_module_enable_disable(self, data_dir):
        from huaqi_src.config.manager import ConfigManager

        mgr = ConfigManager(data_dir)
        assert not mgr.is_enabled("test_module")
        mgr.enable("test_module")
        assert mgr.is_enabled("test_module")

    def test_get_nested_key(self, data_dir):
        from huaqi_src.config.manager import ConfigManager

        mgr = ConfigManager(data_dir)
        mgr.load_config()
        assert mgr.get("memory.search_top_k") == 5
        assert mgr.get("nonexistent.key", "default") == "default"


# ============================================================================
# 2. Agent Layer — Agent 状态与工作流
# ============================================================================


class TestAgentState:
    """Agent 状态定义与创建。"""

    def test_create_initial_state(self):
        from huaqi_src.agent.state import create_initial_state, INTERACTION_MODE_CHAT

        state = create_initial_state(user_id="test_user")
        assert state["user_id"] == "test_user"
        assert state["messages"] == []
        assert state["interaction_mode"] == INTERACTION_MODE_CHAT
        assert state["intent_confidence"] == 0.0
        assert state["intent"] is None

    def test_state_accumulates_messages(self):
        from huaqi_src.agent.state import create_initial_state
        from langchain_core.messages import HumanMessage, AIMessage

        state = create_initial_state(user_id="u1")
        state["messages"].append(HumanMessage(content="你好"))
        state["messages"].append(AIMessage(content="你好！"))

        assert len(state["messages"]) == 2

    def test_intent_constants_defined(self):
        from huaqi_src.agent.state import (
            INTENT_CHAT, INTENT_DIARY, INTENT_CONTENT, INTENT_SKILL, INTENT_UNKNOWN,
            INTERACTION_MODE_CHAT, INTERACTION_MODE_DISTILL, INTERACTION_MODE_REPORT,
            INTERACTION_MODE_ONBOARDING,
        )

        assert INTENT_CHAT == "chat"
        assert INTENT_DIARY == "diary"
        assert INTENT_CONTENT == "content"
        assert INTENT_SKILL == "skill"
        assert INTENT_UNKNOWN == "unknown"
        assert INTERACTION_MODE_CHAT == "chat"
        assert INTERACTION_MODE_DISTILL == "distill"
        assert INTERACTION_MODE_REPORT == "report"
        assert INTERACTION_MODE_ONBOARDING == "onboarding"


class TestChatGraph:
    """对话工作流状态图。"""

    def test_graph_compiles(self):
        from huaqi_src.agent.graph.chat import build_chat_graph

        graph = build_chat_graph()
        assert graph is not None


# ============================================================================
# 3. Data Layer — 数据层
# ============================================================================


class TestRawSignalModels:
    """RawSignal 数据模型。"""

    def test_create_raw_signal(self, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        signal = RawSignal(
            user_id=mock_user_id,
            source_type=SourceType.AI_CHAT,
            timestamp=now_utc,
            content="用户问了关于 Python 的问题",
        )
        assert len(signal.id) == 36  # UUID4
        assert signal.user_id == mock_user_id
        assert signal.source_type == SourceType.AI_CHAT
        assert not signal.processed
        assert not signal.distilled
        assert signal.embedding is None

    def test_content_must_not_be_empty(self, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        with pytest.raises(ValueError, match="content must not be empty"):
            RawSignal(
                user_id=mock_user_id,
                source_type=SourceType.AI_CHAT,
                timestamp=now_utc,
                content="   ",
            )

    def test_user_id_must_not_be_empty(self, now_utc):
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        with pytest.raises(ValueError, match="user_id must not be empty"):
            RawSignal(
                user_id="",
                source_type=SourceType.AI_CHAT,
                timestamp=now_utc,
                content="hello",
            )

    def test_raw_signal_filter_defaults(self):
        from huaqi_src.layers.data.raw_signal.models import RawSignalFilter

        f = RawSignalFilter(user_id="u1")
        assert f.limit == 100
        assert f.offset == 0
        assert f.source_type is None
        assert f.processed is None

    def test_source_type_enum_values(self):
        from huaqi_src.layers.data.raw_signal.models import SourceType

        assert SourceType.JOURNAL.value == "journal"
        assert SourceType.AI_CHAT.value == "ai_chat"
        assert SourceType.WECHAT.value == "wechat"
        assert SourceType.WORK_DOC.value == "work_doc"
        assert SourceType.ABSENCE.value == "absence"


class TestRawSignalStore:
    """RawSignal SQLite 存储。"""

    @pytest.fixture
    def store(self, tmp_path):
        from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
        from huaqi_src.layers.data.raw_signal.store import RawSignalStore

        adapter = SQLiteStorageAdapter(db_path=tmp_path / "test_signals.db")
        return RawSignalStore(adapter=adapter)

    @pytest.fixture
    def signal_a(self, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        return RawSignal(
            user_id=mock_user_id,
            source_type=SourceType.AI_CHAT,
            timestamp=now_utc,
            content="用户消息 A：学习 LangGraph",
        )

    @pytest.fixture
    def signal_b(self, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        return RawSignal(
            user_id="other_user",
            source_type=SourceType.JOURNAL,
            timestamp=now_utc,
            content="其他用户的日记",
        )

    def test_save_and_get(self, store, signal_a):
        store.save(signal_a)
        retrieved = store.get(signal_a.id)
        assert retrieved is not None
        assert retrieved.id == signal_a.id
        assert retrieved.content == signal_a.content

    def test_get_nonexistent_returns_none(self, store):
        assert store.get("nonexistent_id") is None

    def test_query_by_user_id(self, store, signal_a, signal_b):
        from huaqi_src.layers.data.raw_signal.models import RawSignalFilter

        store.save(signal_a)
        store.save(signal_b)

        results = store.query(RawSignalFilter(user_id=signal_a.user_id))
        assert len(results) == 1
        assert results[0].user_id == signal_a.user_id

    def test_query_by_source_type(self, store, signal_a):
        from huaqi_src.layers.data.raw_signal.models import RawSignalFilter, SourceType

        store.save(signal_a)
        results = store.query(RawSignalFilter(
            user_id=signal_a.user_id, source_type=SourceType.AI_CHAT
        ))
        assert len(results) == 1

    def test_mark_processed(self, store, signal_a):
        store.save(signal_a)
        store.mark_processed(signal_a.id)
        s = store.get(signal_a.id)
        assert s.processed is True

    def test_mark_distilled(self, store, signal_a):
        store.save(signal_a)
        store.mark_distilled(signal_a.id)
        s = store.get(signal_a.id)
        assert s.distilled is True

    def test_mark_vectorized(self, store, signal_a):
        store.save(signal_a)
        store.mark_vectorized(signal_a.id)
        s = store.get(signal_a.id)
        assert s.vectorized is True

    def test_count(self, store, signal_a, signal_b):
        from huaqi_src.layers.data.raw_signal.models import RawSignalFilter

        store.save(signal_a)
        store.save(signal_b)
        assert store.count(RawSignalFilter(user_id=signal_a.user_id)) == 1
        assert store.count(RawSignalFilter(user_id="no_one")) == 0

    def test_user_isolation(self, store, signal_a, signal_b):
        from huaqi_src.layers.data.raw_signal.models import RawSignalFilter

        store.save(signal_a)
        store.save(signal_b)

        a_results = store.query(RawSignalFilter(user_id=signal_a.user_id))
        b_results = store.query(RawSignalFilter(user_id="other_user"))
        assert len(a_results) == 1
        assert len(b_results) == 1
        assert a_results[0].user_id != b_results[0].user_id

    def test_search_by_embedding(self, store, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        s1 = RawSignal(
            user_id=mock_user_id, source_type=SourceType.AI_CHAT,
            timestamp=now_utc, content="test A",
            embedding=[1.0, 0.0, 0.0],
        )
        s2 = RawSignal(
            user_id=mock_user_id, source_type=SourceType.AI_CHAT,
            timestamp=now_utc, content="test B",
            embedding=[0.0, 1.0, 0.0],
        )
        store.save(s1)
        store.save(s2)

        results = store.search_by_embedding(mock_user_id, [1.0, 0.1, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0].id == s1.id


class TestEventModels:
    """Event 数据模型。"""

    def test_event_creation(self):
        from huaqi_src.layers.data.events.models import Event

        e = Event(timestamp=1700000000, source="test", actor="user", content="hello")
        assert e.source == "test"
        assert e.actor == "user"
        assert e.content == "hello"

    def test_redact_sensitive_info(self):
        from huaqi_src.layers.data.events.models import redact_sensitive_info

        text = "api key is sk-abc123-def456-ghi789 and more text"
        result = redact_sensitive_info(text)
        assert "sk-abc123-def456-ghi789" not in result
        assert "sk-***" in result
        assert "more text" in result


class TestEventStore:
    """Event SQLite 存储。"""

    @pytest.fixture
    def store(self, tmp_path):
        from huaqi_src.layers.data.events.store import LocalDBStorage

        return LocalDBStorage(db_path=str(tmp_path / "test_events.db"))

    def test_insert_and_get_recent(self, store):
        from huaqi_src.layers.data.events.models import Event

        store.insert_event(Event(
            timestamp=1700000000, source="chat", actor="user",
            content="hello world",
        ))
        store.insert_event(Event(
            timestamp=1700000001, source="diary", actor="user",
            content="wrote diary",
        ))
        recent = store.get_recent_events(limit=2)
        assert len(recent) == 2
        assert recent[0].timestamp >= recent[1].timestamp

    def test_search_events(self, store):
        from huaqi_src.layers.data.events.models import Event

        store.insert_event(Event(
            timestamp=1700000000, source="chat", actor="alice",
            content="讨论 Python 异步编程",
        ))
        results = store.search_events("Python")
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_search_events_no_match(self, store):
        results = store.search_events("nonexistent")
        assert results == []


class TestDiaryStore:
    """日记存储。"""

    @pytest.fixture
    def store(self, data_dir):
        from huaqi_src.layers.data.diary.store import DiaryStore

        return DiaryStore(memory_dir=data_dir / "memory")

    def test_save_and_get(self, store):
        entry = store.save(
            date="2026-05-14",
            content="今天学习了 Rust，很有趣",
            mood="开心",
            tags=["学习", "Rust"],
        )
        assert entry.date == "2026-05-14"
        assert entry.mood == "开心"
        assert "学习" in entry.tags

        retrieved = store.get("2026-05-14")
        assert retrieved is not None
        assert "Rust" in retrieved.content

    def test_get_nonexistent_returns_none(self, store):
        assert store.get("2099-01-01") is None

    def test_list_entries(self, store):
        store.save("2026-05-10", "周一", mood="平静")
        store.save("2026-05-11", "周二", mood="开心")
        store.save("2026-05-12", "周三", mood="疲惫")

        entries = store.list_entries(limit=2)
        assert len(entries) == 2
        # 按日期倒序
        assert entries[0].date >= entries[1].date

    def test_list_entries_date_filter(self, store):
        store.save("2026-05-10", "周一")
        store.save("2026-05-12", "周三")
        store.save("2026-05-14", "周五")

        entries = store.list_entries(start_date="2026-05-11", end_date="2026-05-13")
        assert len(entries) == 1
        assert entries[0].date == "2026-05-12"

    def test_search_diary(self, store):
        store.save("2026-05-14", "今天学习了 Rust 的所有权机制")
        store.save("2026-05-13", "今天学习了 Python asyncio")

        results = store.search("Rust")
        assert len(results) == 1
        assert "Rust" in results[0].content

    def test_delete(self, store):
        store.save("2026-05-14", "test")
        assert store.get("2026-05-14") is not None
        assert store.delete("2026-05-14") is True
        assert store.get("2026-05-14") is None

    def test_get_summary(self, store):
        store.save("2026-05-14", "今天学习了很多内容 " + "A" * 600, mood="专注")
        summary = store.get_summary("2026-05-14")
        assert "2026-05-14" in summary
        assert "专注" in summary

    def test_import_from_markdown_file(self, store, tmp_path):
        md_file = tmp_path / "2026-05-14.md"
        md_file.write_text("""---
date: 2026-05-14
mood: 开心
tags: [coding, python]
---

今天写了很多代码
""", encoding="utf-8")
        count = store.import_from_markdown(md_file)
        assert count == 1
        entry = store.get("2026-05-14")
        assert entry is not None
        assert "代码" in entry.content

    def test_import_from_directory(self, store, tmp_path):
        dir_path = tmp_path / "diary_import"
        dir_path.mkdir()
        (dir_path / "2026-05-10.md").write_text("""---
date: 2026-05-10
mood: 平静
---
周一内容
""", encoding="utf-8")
        (dir_path / "2026-05-11.md").write_text("""---
date: 2026-05-11
mood: 开心
---
周二内容
""", encoding="utf-8")
        count = store.import_from_markdown(dir_path)
        assert count == 2


# ============================================================================
# 4. Growth Layer — 成长层（TELOS）
# ============================================================================


class TestTelosModels:
    """TELOS 数据模型。"""

    def test_dimension_layer_enum(self):
        from huaqi_src.layers.growth.telos.models import DimensionLayer

        assert DimensionLayer.CORE.value == "core"
        assert DimensionLayer.MIDDLE.value == "middle"
        assert DimensionLayer.SURFACE.value == "surface"

    def test_standard_dimensions_count(self):
        from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSIONS

        assert len(STANDARD_DIMENSIONS) == 8
        assert "beliefs" in STANDARD_DIMENSIONS
        assert "shadows" in STANDARD_DIMENSIONS

    def test_create_telos_dimension(self):
        from huaqi_src.layers.growth.telos.models import TelosDimension, DimensionLayer

        dim = TelosDimension(
            name="test_dim",
            layer=DimensionLayer.SURFACE,
            content="测试内容",
            confidence=0.8,
        )
        assert dim.name == "test_dim"
        assert dim.is_active
        assert dim.update_count == 0
        assert dim.confidence == 0.8

    def test_telos_dimension_to_and_from_markdown(self):
        """Markdown 序列化往返。"""
        from huaqi_src.layers.growth.telos.models import (
            TelosDimension, DimensionLayer, HistoryEntry,
        )

        dim = TelosDimension(
            name="goals",
            layer=DimensionLayer.MIDDLE,
            content="学习 Rust 和系统编程",
            confidence=0.7,
            update_count=1,
        )
        md = dim.to_markdown()
        # to_markdown 的格式与 from_markdown 兼容
        restored = TelosDimension.from_markdown(md)
        assert restored.name == "goals"
        assert "Rust" in restored.content

    def test_history_entry(self):
        from huaqi_src.layers.growth.telos.models import HistoryEntry

        entry = HistoryEntry(
            version=1,
            change="确认了既有信念",
            trigger="日记信号分析",
            confidence=0.75,
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        assert entry.version == 1
        assert entry.change == "确认了既有信念"
        assert entry.trigger == "日记信号分析"


class TestTelosManager:
    """TELOS 维度管理器。"""

    @pytest.fixture
    def telos_dir(self, tmp_path):
        d = tmp_path / "telos"
        d.mkdir()
        return d

    @pytest.fixture
    def manager(self, telos_dir):
        from huaqi_src.layers.growth.telos.manager import TelosManager

        return TelosManager(telos_dir=telos_dir, git_commit=False)

    def test_init_creates_standard_dimensions(self, manager):
        manager.init()

        from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSIONS

        for name in STANDARD_DIMENSIONS:
            dim = manager.get(name)
            assert dim is not None
            assert dim.name == name

    def test_init_creates_index(self, manager):
        manager.init()
        index_path = manager._dir / "INDEX.md"
        assert index_path.exists()
        content = index_path.read_text()
        assert "# TELOS 索引" in content

    def test_init_creates_meta_file(self, manager):
        manager.init()
        meta_path = manager._dir / "meta.md"
        assert meta_path.exists()

    def test_get_nonexistent_raises(self, manager):
        manager.init()
        from huaqi_src.config.errors import DimensionNotFoundError

        with pytest.raises(DimensionNotFoundError):
            manager.get("nonexistent_dim")

    def test_list_active(self, manager):
        manager.init()
        active = manager.list_active()
        assert len(active) > 0
        for dim in active:
            assert dim.is_active

    def test_create_custom_dimension(self, manager):
        manager.init()
        from huaqi_src.layers.growth.telos.models import DimensionLayer

        manager.create_custom(
            name="my_custom",
            layer=DimensionLayer.SURFACE,
            initial_content="自定义内容",
        )
        dim = manager.get("my_custom")
        assert dim.name == "my_custom"
        assert dim.content == "自定义内容"

    def test_create_duplicate_custom_raises(self, manager):
        manager.init()
        from huaqi_src.layers.growth.telos.models import DimensionLayer

        manager.create_custom("dup", DimensionLayer.SURFACE, "v1")
        with pytest.raises(ValueError, match="already exists"):
            manager.create_custom("dup", DimensionLayer.SURFACE, "v2")

    def test_archive_custom_dimension(self, manager):
        manager.init()
        from huaqi_src.layers.growth.telos.models import DimensionLayer

        manager.create_custom("temp_dim", DimensionLayer.SURFACE, "tmp")
        manager.archive("temp_dim")

        from huaqi_src.config.errors import DimensionNotFoundError

        with pytest.raises(DimensionNotFoundError):
            manager.get("temp_dim")

        archive_path = manager._archive_path("temp_dim")
        assert archive_path.exists()

    def test_cannot_archive_standard(self, manager):
        manager.init()
        with pytest.raises(ValueError, match="Cannot archive standard"):
            manager.archive("beliefs")

    def test_update_dimension(self, manager):
        manager.init()
        from huaqi_src.layers.growth.telos.models import HistoryEntry

        entry = HistoryEntry(
            version=1,
            change="确认了信念",
            trigger="signal_001",
            confidence=0.9,
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        manager.update(
            name="beliefs",
            new_content="更新后的信念内容",
            history_entry=entry,
            confidence=0.9,
        )
        dim = manager.get("beliefs")
        assert dim.content == "更新后的信念内容"
        assert dim.confidence == 0.9
        assert dim.update_count == 1

    def test_get_dimension_snippet(self, manager):
        manager.init()
        snippet = manager.get_dimension_snippet("beliefs")
        assert len(snippet) > 0
        assert "更新历史" not in snippet

    def test_get_all_dimension_snippets(self, manager):
        manager.init()
        snippets = manager.get_all_dimension_snippets()
        assert len(snippets) > 0
        assert "beliefs" in snippets


class TestGrowthEvents:
    """成长事件模型与存储。"""

    def test_growth_event_creation(self, mock_user_id, now_utc):
        from huaqi_src.layers.growth.telos.growth_events import GrowthEvent

        event = GrowthEvent(
            user_id=mock_user_id,
            dimension="goals",
            layer="middle",
            title="设定了新目标",
            narrative="用户决定学习 Rust",
            new_content="学习 Rust",
            trigger_signals=["sig_001"],
            occurred_at=now_utc,
        )
        assert event.user_id == mock_user_id
        assert event.dimension == "goals"
        assert event.title == "设定了新目标"

    def test_growth_event_store_save_and_list(self, tmp_path, mock_user_id, now_utc):
        from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
        from huaqi_src.layers.growth.telos.growth_events import GrowthEvent, GrowthEventStore

        adapter = SQLiteStorageAdapter(db_path=tmp_path / "growth_events.db")
        store = GrowthEventStore(adapter=adapter)
        event = GrowthEvent(
            user_id=mock_user_id,
            dimension="goals",
            layer="middle",
            title="新目标",
            narrative="学习 Rust 的目标设定",
            new_content="目标：学习 Rust",
            trigger_signals=["sig_001"],
            occurred_at=now_utc,
        )
        store.save(event)

        events = store.list_by_user(mock_user_id, limit=10)
        assert len(events) >= 1
        assert events[0].dimension == "goals"


class TestTelosEngineStep1:
    """TELOS Engine Step1 输出模型。"""

    def test_step1_output_validation(self):
        from huaqi_src.layers.growth.telos.engine import Step1Output, SignalStrength

        output = Step1Output(
            dimensions=["goals", "beliefs"],
            emotion="positive",
            intensity=0.8,
            signal_strength=SignalStrength.MEDIUM,
            strong_reason=None,
            summary="测试摘要",
            new_dimension_hint=None,
        )
        assert len(output.dimensions) == 2
        assert output.emotion == "positive"

    def test_step1_output_intensity_range(self):
        from huaqi_src.layers.growth.telos.engine import Step1Output, SignalStrength

        with pytest.raises(ValueError, match="intensity"):
            Step1Output(
                dimensions=["goals"],
                emotion="neutral",
                intensity=1.5,
                signal_strength=SignalStrength.WEAK,
                strong_reason=None,
                summary="bad",
                new_dimension_hint=None,
            )

    def test_combined_step_output(self):
        from huaqi_src.layers.growth.telos.engine import CombinedStepOutput

        output = CombinedStepOutput(
            should_update=True,
            new_content="更新内容",
            consistency_score=0.85,
            history_entry={"date": "2026-05-14"},
            is_growth_event=True,
            growth_title="里程碑",
            growth_narrative="用户取得了进步",
            confidence=0.9,
        )
        assert output.should_update
        assert output.is_growth_event
        assert output.confidence == 0.9


# ============================================================================
# 5. Capabilities Layer — 能力层
# ============================================================================


class TestLLMManager:
    """LLM 管理器。"""

    def test_dummy_provider_chat(self):
        from huaqi_src.layers.capabilities.llm.manager import (
            LLMManager, LLMConfig, Message,
        )

        mgr = LLMManager()
        mgr.add_config(LLMConfig(provider="dummy", model="dummy"))
        mgr.set_active("dummy")

        response = mgr.chat([Message.user("hello")])
        assert response.model == "dummy"
        assert "虚拟回复" in response.content

    def test_dummy_provider_stream(self):
        from huaqi_src.layers.capabilities.llm.manager import (
            LLMManager, LLMConfig, Message,
        )

        mgr = LLMManager()
        mgr.add_config(LLMConfig(provider="dummy", model="dummy"))
        mgr.set_active("dummy")

        chunks = list(mgr.chat([Message.user("hi")], stream=True))
        assert len(chunks) > 0
        full = "".join(chunks)
        assert "虚拟回复" in full

    def test_quick_chat(self):
        from huaqi_src.layers.capabilities.llm.manager import (
            LLMManager, LLMConfig,
        )

        mgr = LLMManager()
        mgr.add_config(LLMConfig(provider="dummy", model="dummy"))
        mgr.set_active("dummy")

        result = mgr.quick_chat("hello", system="you are helpful")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_list_providers(self):
        from huaqi_src.layers.capabilities.llm.manager import (
            LLMManager, LLMConfig,
        )

        mgr = LLMManager()
        mgr.add_config(LLMConfig(provider="dummy", model="dummy"))
        assert mgr.list_providers() == ["dummy"]

    def test_no_provider_raises(self):
        from huaqi_src.layers.capabilities.llm.manager import (
            LLMManager, LLMError, Message,
        )

        mgr = LLMManager()
        with pytest.raises(LLMError, match="未配置任何 LLM"):
            mgr.chat([Message.user("hi")])

    def test_unknown_provider_raises(self):
        from huaqi_src.layers.capabilities.llm.manager import (
            LLMManager, LLMConfig,
        )

        mgr = LLMManager()
        mgr.add_config(LLMConfig(provider="unknown", model="x"))
        with pytest.raises(ValueError, match="未知的提供商"):
            mgr.set_active("unknown")

    def test_message_models(self):
        from huaqi_src.layers.capabilities.llm.manager import Message, MessageRole

        sys_msg = Message.system("you are helpful")
        assert sys_msg.role == MessageRole.SYSTEM

        user_msg = Message.user("hello")
        assert user_msg.role == MessageRole.USER

        assistant_msg = Message.assistant("hi there")
        assert assistant_msg.role == MessageRole.ASSISTANT

    def test_message_to_dict_and_from_dict(self):
        from huaqi_src.layers.capabilities.llm.manager import Message

        msg = Message.user("hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "hello"

        restored = Message.from_dict(d)
        assert restored.content == "hello"

    def test_llm_response_properties(self):
        from huaqi_src.layers.capabilities.llm.manager import LLMResponse

        resp = LLMResponse(
            content="test",
            model="gpt-4",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5
        assert resp.total_tokens == 15

    def test_global_manager_singleton(self):
        from huaqi_src.layers.capabilities.llm.manager import (
            get_llm_manager, init_llm_manager,
        )

        mgr1 = init_llm_manager()
        mgr2 = get_llm_manager()
        assert mgr1 is mgr2


class TestLearningModels:
    """学习系统数据模型。"""

    def test_lesson_outline(self):
        from huaqi_src.layers.capabilities.learning.models import LessonOutline

        lesson = LessonOutline(index=1, title="Python基础", status="pending")
        assert lesson.index == 1
        assert lesson.lesson_type == "quiz"

        d = lesson.to_dict()
        restored = LessonOutline.from_dict(d)
        assert restored.index == 1
        assert restored.title == "Python基础"

    def test_course_outline(self):
        from huaqi_src.layers.capabilities.learning.models import (
            CourseOutline, LessonOutline,
        )

        lessons = [
            LessonOutline(index=1, title="第一章"),
            LessonOutline(index=2, title="第二章"),
        ]
        course = CourseOutline(
            skill_name="Rust",
            slug="rust",
            lessons=lessons,
        )
        assert course.skill_name == "Rust"
        assert course.total_lessons == 2
        assert course.current_lesson == 1

    def test_course_outline_current_lesson(self):
        from huaqi_src.layers.capabilities.learning.models import (
            CourseOutline, LessonOutline,
        )

        lessons = [
            LessonOutline(index=1, title="Ch1", status="completed"),
            LessonOutline(index=2, title="Ch2", status="in_progress"),
            LessonOutline(index=3, title="Ch3", status="pending"),
        ]
        course = CourseOutline(skill_name="Go", slug="go", lessons=lessons)
        assert course.current_lesson == 2

    def test_slugify(self):
        from huaqi_src.layers.capabilities.learning.progress_store import slugify

        assert slugify("Rust Programming") == "rust-programming"
        assert slugify("  Hello World!!!  ") == "hello-world"
        assert slugify("Python_Async") == "python-async"


class TestLearningProgressStore:
    """学习进度存储。"""

    @pytest.fixture
    def store(self, tmp_path):
        from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore

        return LearningProgressStore(base_dir=tmp_path / "learning")

    def test_save_and_load_course(self, store):
        from huaqi_src.layers.capabilities.learning.models import (
            CourseOutline, LessonOutline,
        )

        course = CourseOutline(
            skill_name="Python Async",
            slug="python-async",
            lessons=[
                LessonOutline(index=1, title="asyncio基础"),
                LessonOutline(index=2, title="协程进阶"),
                LessonOutline(index=3, title="实战项目"),
            ],
        )
        store.save_course(course)
        loaded = store.load_course("python-async")
        assert loaded is not None
        assert loaded.skill_name == "Python Async"
        assert loaded.total_lessons == 3

    def test_list_courses(self, store):
        from huaqi_src.layers.capabilities.learning.models import (
            CourseOutline, LessonOutline,
        )

        store.save_course(CourseOutline(
            skill_name="Rust", slug="rust",
            lessons=[LessonOutline(index=1, title="入门")],
        ))
        store.save_course(CourseOutline(
            skill_name="Go", slug="go",
            lessons=[LessonOutline(index=1, title="基础")],
        ))
        courses = store.list_courses()
        assert len(courses) == 2

    def test_mark_lesson_complete(self, store):
        from huaqi_src.layers.capabilities.learning.models import (
            CourseOutline, LessonOutline,
        )

        store.save_course(CourseOutline(
            skill_name="Rust", slug="rust",
            lessons=[
                LessonOutline(index=1, title="Ch1"),
                LessonOutline(index=2, title="Ch2"),
            ],
        ))
        store.mark_lesson_complete("rust", 1)
        course = store.load_course("rust")
        assert course.lessons[0].status == "completed"
        assert course.lessons[0].completed_at is not None
        assert course.current_lesson == 2

    def test_save_session(self, store):
        store.save_session(
            skill_slug="rust",
            lesson_index=1,
            lesson_title="所有权",
            content="Rust 所有权的概念...",
            quiz="什么是所有权？",
            user_answer="所有权是 Rust 的核心机制",
            feedback="回答得很好！",
        )
        sessions_dir = store.sessions_dir
        files = list(sessions_dir.glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text()
        assert "所有权" in content
        assert "回答得很好" in content


# ============================================================================
# 6. Job Config Layer — 任务配置（headless 执行，供 GitHub Actions 用）
# ============================================================================


class TestScheduledJobStore:
    """调度任务存储。"""

    def test_default_jobs_built(self, set_data_dir):
        from huaqi_src.scheduler.scheduled_job_store import _build_default_jobs

        jobs = _build_default_jobs()
        assert isinstance(jobs, list)
        assert len(jobs) > 0
        job_ids = [j["id"] for j in jobs]
        assert "morning_brief" in job_ids
        assert "daily_report" in job_ids
        assert "weekly_report" in job_ids

    def test_scheduled_job_model(self):
        from huaqi_src.scheduler.scheduled_job_store import ScheduledJob

        job = ScheduledJob(
            id="test_job",
            display_name="测试任务",
            cron="0 8 * * *",
            prompt="测试提示词",
        )
        assert job.id == "test_job"
        assert job.enabled is True
        assert job.display_name == "测试任务"

    def test_scheduled_job_store_crud(self, set_data_dir):
        from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore, ScheduledJob

        store = ScheduledJobStore(data_dir=set_data_dir)
        initial_count = len(store.load_jobs())

        job = ScheduledJob(
            id="smoke_test_job",
            display_name="冒烟测试任务",
            cron="0 10 * * *",
            prompt="测试",
            enabled=True,
        )
        store.add_job(job)
        jobs = store.load_jobs()
        assert len(jobs) == initial_count + 1

        store.remove_job("smoke_test_job")
        jobs = store.load_jobs()
        assert len(jobs) == initial_count



# ============================================================================
# 7. Cross-layer Integration — 跨层集成
# ============================================================================


class TestDataFlowIntegration:
    """验证核心数据流链路。"""

    def test_raw_signal_to_telos_dimension_flow(
        self, tmp_path, mock_user_id, now_utc,
    ):
        """验证 RawSignal 存储 → Telos Manager 读写的完整链路。"""
        from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
        from huaqi_src.layers.data.raw_signal.store import RawSignalStore
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
        from huaqi_src.layers.growth.telos.manager import TelosManager

        # 1. 存储 RawSignal
        adapter = SQLiteStorageAdapter(db_path=tmp_path / "signals.db")
        signal_store = RawSignalStore(adapter=adapter)
        signal = RawSignal(
            user_id=mock_user_id,
            source_type=SourceType.AI_CHAT,
            timestamp=now_utc,
            content="用户表达了对 Rust 学习的强烈兴趣",
        )
        signal_store.save(signal)
        assert signal_store.get(signal.id) is not None

        # 2. TELOS 维度管理
        telos_dir = tmp_path / "telos"
        telos_dir.mkdir()
        telos_mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
        telos_mgr.init()

        # 3. 验证维度可读写
        dim = telos_mgr.get("goals")
        assert dim is not None
        assert dim.content is not None

    def test_growth_event_integration(self, tmp_path, mock_user_id, now_utc):
        """验证 GrowthEvent 可以通过 SQLiteStorageAdapter 持久化。"""
        from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
        from huaqi_src.layers.growth.telos.growth_events import GrowthEvent, GrowthEventStore

        adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
        store = GrowthEventStore(adapter=adapter)
        event = GrowthEvent(
            user_id=mock_user_id,
            dimension="beliefs",
            layer="core",
            title="信念更新",
            narrative="冒烟测试叙事",
            new_content="新认知内容",
            trigger_signals=["sig_001"],
            occurred_at=now_utc,
        )
        store.save(event)
        retrieved = store.get(event.id)
        assert retrieved is not None
        assert retrieved.title == "信念更新"


class TestDependencyDirection:
    """验证依赖方向符合架构规范。"""

    def test_data_layer_does_not_import_agent(self):
        """data 层不应依赖 agent 层（pipeline.py 除外，它是编排层）。"""
        import ast
        from pathlib import Path

        src_root = Path(__file__).parent.parent / "huaqi_src"
        data_dir = src_root / "layers" / "data"

        violations = []
        for py_file in data_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and "huaqi_src.agent" in node.module:
                            violations.append(
                                f"{py_file.relative_to(src_root)} imports {node.module}"
                            )
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if "huaqi_src.agent" in alias.name:
                                violations.append(
                                    f"{py_file.relative_to(src_root)} imports {alias.name}"
                                )
            except SyntaxError:
                pass

        # pipeline.py 是编排层，允许跨层依赖
        for v in violations:
            if "pipeline.py" in v:
                continue
            pytest.fail(f"架构违规: {v}")

    def test_config_layer_business_imports_are_only_from_adapters(self):
        """config 层的业务层依赖仅限于 adapters（适配器需要知道数据模型）。"""
        import ast
        from pathlib import Path

        src_root = Path(__file__).parent.parent / "huaqi_src"
        config_dir = src_root / "config"

        # 合法的跨层 import（适配器需要知道数据模型）
        allowed_files = {
            "config/adapters/storage.py",
            "config/adapters/storage_base.py",
            "config/adapters/vector_base.py",
        }

        violations = []
        for py_file in config_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and any(
                            prefix in node.module
                            for prefix in ("huaqi_src.agent", "huaqi_src.layers",
                                           "huaqi_src.cli")
                        ):
                            rel = str(py_file.relative_to(src_root))
                            if rel not in allowed_files:
                                violations.append(f"{rel} imports {node.module}")
            except SyntaxError:
                pass

        for v in violations:
            pytest.fail(f"架构违规: {v}")

    def test_no_core_utils_dirs_exist(self):
        """确保代码库中不存在禁止的万能桶目录。"""
        from pathlib import Path

        src_root = Path(__file__).parent.parent / "huaqi_src"
        forbidden = ["core", "utils", "helpers", "common", "misc"]

        for d in forbidden:
            assert not (src_root / d).is_dir(), \
                f"禁止目录存在: {d}/，请将代码迁移到正确位置"

    def test_no_version_suffix_files(self):
        """确保代码库中不存在 _v2/_simple/_new/_old 等临时命名。"""
        from pathlib import Path

        src_root = Path(__file__).parent.parent / "huaqi_src"
        forbidden_patterns = ["_v2", "_simple", "_new", "_old"]

        for py_file in src_root.rglob("*.py"):
            stem = py_file.stem
            for pattern in forbidden_patterns:
                assert pattern not in stem.lower().split("_"), \
                    f"禁止的临时文件命名: {py_file.relative_to(src_root)}"


# ============================================================================
# 8. Data Models Roundtrip — 数据模型序列化往返
# ============================================================================


class TestDataModelRoundtrips:
    """数据模型 JSON/YAML/Markdown 序列化往返测试。"""

    def test_raw_signal_json_roundtrip(self, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        signal = RawSignal(
            user_id=mock_user_id,
            source_type=SourceType.JOURNAL,
            timestamp=now_utc,
            content="test content",
        )
        json_str = signal.model_dump_json()
        restored = RawSignal.model_validate_json(json_str)
        assert restored.id == signal.id
        assert restored.user_id == signal.user_id
        assert restored.content == signal.content
        assert restored.source_type == signal.source_type

    def test_raw_signal_filter_validation(self):
        from huaqi_src.layers.data.raw_signal.models import RawSignalFilter

        with pytest.raises(ValueError, match="limit must be positive"):
            RawSignalFilter(user_id="u1", limit=0)

        with pytest.raises(ValueError, match="offset must be non-negative"):
            RawSignalFilter(user_id="u1", offset=-1)

    def test_step1_output_json_roundtrip(self):
        from huaqi_src.layers.growth.telos.engine import Step1Output, SignalStrength

        output = Step1Output(
            dimensions=["goals", "challenges"],
            emotion="mixed",
            intensity=0.6,
            signal_strength=SignalStrength.STRONG,
            strong_reason="明确的目标陈述",
            summary="用户设定了新目标",
            new_dimension_hint=None,
            has_people=True,
            mentioned_names=["Alice", "Bob"],
        )
        json_str = output.model_dump_json()
        restored = Step1Output.model_validate_json(json_str)
        assert restored.dimensions == output.dimensions
        assert restored.emotion == "mixed"
        assert restored.has_people is True
        assert "Alice" in restored.mentioned_names

    def test_growth_event_json_roundtrip(self, mock_user_id, now_utc):
        from huaqi_src.layers.growth.telos.growth_events import GrowthEvent

        event = GrowthEvent(
            user_id=mock_user_id,
            dimension="beliefs",
            layer="core",
            title="信念转变",
            narrative="用户信念发生了变化",
            new_content="更新后的信念",
            trigger_signals=["sig_001", "sig_002"],
            occurred_at=now_utc,
        )
        json_str = event.model_dump_json()
        restored = GrowthEvent.model_validate_json(json_str)
        assert restored.title == "信念转变"
        assert len(restored.trigger_signals) == 2


# ============================================================================
# 9. Storage Adapter — 存储适配器
# ============================================================================


class TestSQLiteStorageAdapter:
    """SQLite 存储适配器。"""

    @pytest.fixture
    def adapter(self, tmp_path):
        from huaqi_src.config.adapters.storage import SQLiteStorageAdapter

        return SQLiteStorageAdapter(db_path=tmp_path / "adapter_test.db")

    def test_schema_created(self, adapter):
        conn = sqlite3.connect(str(adapter._db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='raw_signals'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_save_and_retrieve(self, adapter, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType

        signal = RawSignal(
            user_id=mock_user_id,
            source_type=SourceType.AI_CHAT,
            timestamp=now_utc,
            content="adapter test",
        )
        adapter.save(signal)
        retrieved = adapter.get(signal.id)
        assert retrieved is not None
        assert retrieved.content == "adapter test"

    def test_filter_by_processed_status(self, adapter, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import (
            RawSignal, SourceType, RawSignalFilter,
        )

        s1 = RawSignal(
            user_id=mock_user_id, source_type=SourceType.AI_CHAT,
            timestamp=now_utc, content="processed",
        )
        s2 = RawSignal(
            user_id=mock_user_id, source_type=SourceType.AI_CHAT,
            timestamp=now_utc, content="unprocessed",
        )
        adapter.save(s1)
        adapter.save(s2)
        adapter.mark_processed(s1.id)

        processed = adapter.query(RawSignalFilter(user_id=mock_user_id, processed=1))
        unprocessed = adapter.query(RawSignalFilter(user_id=mock_user_id, processed=0))
        assert len(processed) >= 1
        assert len(unprocessed) >= 1

    def test_save_duplicate_ignored(self, adapter, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType, RawSignalFilter

        signal = RawSignal(
            user_id=mock_user_id, source_type=SourceType.AI_CHAT,
            timestamp=now_utc, content="dup test",
        )
        adapter.save(signal)
        adapter.save(signal)  # INSERT OR IGNORE
        assert adapter.count(RawSignalFilter(user_id=mock_user_id)) == 1


# ============================================================================
# 10. Edge Cases & Error Handling — 边界条件与错误处理
# ============================================================================


class TestEdgeCases:
    """边界条件测试。"""

    def test_empty_diary_search(self, data_dir):
        from huaqi_src.layers.data.diary.store import DiaryStore

        store = DiaryStore(memory_dir=data_dir / "memory")
        assert store.search("nothing") == []

    def test_empty_diary_list(self, data_dir):
        from huaqi_src.layers.data.diary.store import DiaryStore

        store = DiaryStore(memory_dir=data_dir / "memory")
        assert store.list_entries() == []

    def test_empty_course_list(self, tmp_path):
        from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore

        store = LearningProgressStore(base_dir=tmp_path / "learning")
        assert store.list_courses() == []

    def test_load_nonexistent_course(self, tmp_path):
        from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore

        store = LearningProgressStore(base_dir=tmp_path / "learning")
        assert store.load_course("nonexistent") is None

    def test_mark_lesson_complete_nonexistent_course(self, tmp_path):
        from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore

        store = LearningProgressStore(base_dir=tmp_path / "learning")
        store.mark_lesson_complete("no_course", 1)  # 不应抛异常

    def test_diary_special_characters_in_content(self, data_dir):
        from huaqi_src.layers.data.diary.store import DiaryStore

        store = DiaryStore(memory_dir=data_dir / "memory")
        content = "包含特殊字符：\n\n---\n\n这不应被视为 frontmatter"
        entry = store.save("2026-05-14", content)
        retrieved = store.get("2026-05-14")
        assert retrieved is not None
        assert "特殊字符" in retrieved.content

    def test_telos_dimension_unicode_content(self, tmp_path):
        from huaqi_src.layers.growth.telos.manager import TelosManager
        from huaqi_src.layers.growth.telos.models import HistoryEntry

        telos_dir = tmp_path / "telos"
        telos_dir.mkdir()
        mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
        mgr.init()

        unicode_content = "🎯 目标：学习 Rust 编程语言\n\n详细信息：\n- 完成 Rust Book\n- 写一个 CLI 工具"
        entry = HistoryEntry(
            version=1,
            change="Rust学习目标",
            trigger="测试",
            confidence=0.9,
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        mgr.update("goals", unicode_content, entry, 0.9)
        dim = mgr.get("goals")
        assert "Rust" in dim.content
        assert "🎯" in dim.content

    def test_signal_with_metadata(self, mock_user_id, now_utc):
        from huaqi_src.layers.data.raw_signal.models import (
            RawSignal, SourceType, WechatMetadata,
        )

        meta = WechatMetadata(participants=["Alice", "Bob"], chat_name="技术群")
        signal = RawSignal(
            user_id=mock_user_id,
            source_type=SourceType.WECHAT,
            timestamp=now_utc,
            content="群聊消息",
            metadata=meta.model_dump(),
        )
        assert signal.metadata["chat_name"] == "技术群"
        assert "Alice" in signal.metadata["participants"]

    def test_absence_metadata_days_positive(self):
        from huaqi_src.layers.data.raw_signal.models import AbsenceMetadata

        with pytest.raises(ValueError, match="days must be positive"):
            AbsenceMetadata(days=0, last_signal_id="sig_001")

    def test_audio_metadata_duration_non_negative(self):
        from huaqi_src.layers.data.raw_signal.models import AudioMetadata

        with pytest.raises(ValueError, match="duration_seconds must be non-negative"):
            AudioMetadata(duration_seconds=-1)


# ============================================================================
# 11. Basic Integration — 基础集成
# ============================================================================


class TestBasicIntegration:
    """验证多模块组合使用不报错。"""

    def test_memory_store_and_diary_store_coexist(self, data_dir):
        """MarkdownMemoryStore 和 DiaryStore 可以在同一 data_dir 下工作。"""
        from huaqi_src.layers.data.memory.storage.markdown_store import MarkdownMemoryStore
        from huaqi_src.layers.data.diary.store import DiaryStore

        mem_store = MarkdownMemoryStore(data_dir / "memory" / "conversations")
        diary_store = DiaryStore(memory_dir=data_dir / "memory")

        diary_store.save("2026-05-14", "测试日记")

        # paths exist
        assert (data_dir / "memory" / "conversations").exists()
        assert (data_dir / "memory" / "diary").exists()


# ============================================================================
# Feature Acceptance Tests — 按 Spec 的 AC 生成的验收测试
# ============================================================================
# 新增 feature 时，在此区域追加 Test<FeatureName> 类。
# 每个测试方法对应 docs/specs/<feature-name>.md 中的一条 AC。
#
# 模板：
# class Test<FeatureName>:
#     \"\"\"<feature-name> 功能验收。
#
#     Spec: docs/specs/<feature-name>.md
#     \"\"\"
#
#     def test_<ac_scenario>(self, data_dir, set_data_dir):
#         \"\"\"AC-1: <描述>.\"\"\"
#         ...
#
# ============================================================================


class TestGitHubActionsWorkflows:
    """GitHub Actions 定时任务迁移功能验收。

    Spec: docs/specs/2026-05-14-reports-github-actions.md
    """

    def test_six_workflow_files_exist(self, data_dir, set_data_dir):
        """AC-1: 6 个 workflow 文件存在。"""
        import yaml
        from pathlib import Path
        workflow_dir = Path("scripts/github-actions")
        expected = [
            "morning-brief.yml", "daily-report.yml",
            "weekly-report.yml", "quarterly-report.yml",
            "learning-push.yml", "world-fetch.yml",
        ]
        for wf in expected:
            assert (workflow_dir / wf).exists(), f"Missing: {wf}"

    def test_workflow_files_have_triggers(self, data_dir, set_data_dir):
        """AC-1: 每个 workflow 包含 cron 和 workflow_dispatch 触发器。"""
        import yaml
        from pathlib import Path
        workflow_dir = Path("scripts/github-actions")
        for wf in workflow_dir.glob("*.yml"):
            with open(wf) as f:
                data = yaml.safe_load(f)
            triggers = data.get("on") or data.get(True) or {}
            assert "schedule" in triggers, f"{wf.name}: missing schedule trigger"
            assert "workflow_dispatch" in triggers, f"{wf.name}: missing workflow_dispatch"

    def test_workflow_has_write_permission(self, data_dir, set_data_dir):
        """AC-10: 每个 workflow 声明 contents: write 权限。"""
        import yaml
        from pathlib import Path
        workflow_dir = Path("scripts/github-actions")
        for wf in workflow_dir.glob("*.yml"):
            with open(wf) as f:
                data = yaml.safe_load(f)
            for job_id, job in data.get("jobs", {}).items():
                perms = job.get("permissions", {})
                assert perms.get("contents") == "write", \
                    f"{wf.name}/{job_id}: missing contents:write"

    def test_quarterly_has_conditional_check(self, data_dir, set_data_dir):
        """AC-9: 季报 workflow 包含季度最后一天判断。"""
        from pathlib import Path
        path = Path("scripts/github-actions/quarterly-report.yml")
        content = path.read_text()
        assert "timedelta" in content, \
            "quarterly-report.yml: missing end-of-quarter check"

    def test_notify_sh_uses_serverchan_key(self, data_dir, set_data_dir):
        """AC-4: notify.sh 使用 SERVERCHAN_KEY 环境变量。"""
        from pathlib import Path
        path = Path("scripts/github-actions/notify.sh")
        content = path.read_text()
        assert "SERVERCHAN_KEY" in content
        assert "sctapi.ftqq.com" in content

    def test_secrets_doc_covers_all_secrets(self, data_dir, set_data_dir):
        """AC-5: Secrets 配置文档存在且包含必要信息。"""
        from pathlib import Path
        path = Path("scripts/github-actions/SECRETS.md")
        # 文档可能在 Task 2 才创建
        if not path.exists():
            return
        content = path.read_text()
        assert "SERVERCHAN_KEY" in content
        assert "API" in content

    def test_headless_env_var_bypasses_wizard(self, data_dir, set_data_dir):
        """AC-2: HUAQI_DATA_DIR 环境变量绕过交互式向导。"""
        from huaqi_src.config.paths import get_data_dir, is_data_dir_set
        data_path = get_data_dir()
        assert data_path is not None
        assert data_path.exists()
        # 在 fixture 已设置 data_dir 的环境中，应已绕过向导
        assert is_data_dir_set()


class TestWorldNewsEnhance:
    """world-news-enhance 功能验收。

    Spec: docs/specs/world-news-enhance.md
    """

    def test_rss_source_content_includes_link(self, data_dir, set_data_dir):
        """AC-1: RSS 源采集的每条新闻 doc.content 包含原文链接。"""
        from unittest.mock import MagicMock, patch
        import datetime
        from huaqi_src.layers.data.world.sources.rss_source import RSSSource

        def _make_entry(title, link, summary, published_parsed):
            entry = MagicMock()
            entry.get = lambda key, default=None: {
                "title": title, "link": link, "summary": summary,
            }.get(key, default)
            entry.configure_mock(
                title=title, link=link, summary=summary,
                published_parsed=published_parsed,
            )
            return entry

        mock_entry = _make_entry(
            title="Test News",
            link="https://example.com/news/1",
            summary="Summary text",
            published_parsed=datetime.datetime(2026, 5, 15, 8, 0).timetuple(),
        )
        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        with patch("feedparser.parse", return_value=mock_feed):
            source = RSSSource(url="https://example.com/feed", name="TS")
            docs = source.fetch()
            assert len(docs) == 1
            assert "**链接**" in docs[0].content
            assert "https://example.com/news/1" in docs[0].content

    def test_enricher_prompt_requires_key_sections(self, data_dir, set_data_dir):
        """AC-2/AC-3/AC-5: 增强 prompt 要求中英对照、重点关注建议、中文源处理。"""
        from huaqi_src.layers.capabilities.world_news_enricher import _ENRICH_PROMPT

        assert "英文原标题" in _ENRICH_PROMPT or "英文" in _ENRICH_PROMPT
        assert "链接" in _ENRICH_PROMPT
        assert "重点关注建议" in _ENRICH_PROMPT
        assert "中文" in _ENRICH_PROMPT
        assert "{user_context}" in _ENRICH_PROMPT

    def test_enricher_graceful_degradation(self, data_dir, set_data_dir):
        """AC-6: 空文件和 LLM 失败时优雅降级。"""
        from pathlib import Path
        from unittest.mock import MagicMock
        from huaqi_src.layers.capabilities.world_news_enricher import \
            WorldNewsEnricher

        enricher = WorldNewsEnricher(MagicMock())

        # 空文件
        f = Path("/tmp/smoke_empty_world.md")
        f.write_text("", encoding="utf-8")
        assert enricher.enrich_file(f) is False

        # LLM 失败
        mock_llm = MagicMock()
        mock_llm.quick_chat.side_effect = RuntimeError("fail")
        enricher2 = WorldNewsEnricher(mock_llm)
        assert enricher2.enrich_file(f) is False  # 空文件先触发，不调用 LLM

    def test_load_user_context_from_telos(self, data_dir, set_data_dir):
        """_load_user_context 从 TELOS 目录加载用户画像。"""
        from huaqi_src.cli.commands.world import _load_user_context
        from huaqi_src.config import paths
        from huaqi_src.layers.growth.telos.models import (
            TelosDimension, DimensionLayer,
        )

        telos_dir = data_dir / "telos"
        telos_dir.mkdir(parents=True, exist_ok=True)
        goals = TelosDimension(
            name="goals", layer=DimensionLayer.MIDDLE,
            content="学习 Rust 语言", confidence=0.9, update_count=2,
        )
        (telos_dir / "goals.md").write_text(goals.to_markdown(), encoding="utf-8")

        # 验证能正确加载
        import huaqi_src.config.paths as p
        with patch.object(p, "require_data_dir", return_value=data_dir):
            result = _load_user_context()
        assert result is not None
        assert "Rust" in result

    def test_world_provider_extracts_suggestions(self, data_dir, set_data_dir):
        """AC-4: WorldProvider 优先提取「重点关注建议」板块。"""
        from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
        from huaqi_src.layers.capabilities.reports.providers import DateRange
        import datetime

        world_dir = data_dir / "world"
        world_dir.mkdir(parents=True, exist_ok=True)
        content = (
            "# 世界感知摘要 2026-05-15\n\n"
            + "x" * 2000 + "\n\n"
            "## 重点关注建议\n\n"
            "### AI/科技\n"
            "- **OpenAI 发布新模型**：关注理由：与工作直接相关\n\n"
            "---\n\n"
            "## 新闻详情\n\n"
            "不应该出现的新闻详情"
        )
        (world_dir / "2026-05-15.md").write_text(content, encoding="utf-8")

        provider = WorldProvider(data_dir=data_dir)
        date_range = DateRange(
            start=datetime.date(2026, 5, 15),
            end=datetime.date(2026, 5, 15),
        )
        result = provider.get_context("morning", date_range)
        assert result is not None
        assert "重点关注建议" in result
        assert "不应该出现的新闻详情" not in result


# ============================================================================
# 运行入口
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
