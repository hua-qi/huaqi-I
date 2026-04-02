import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import (
    TelosDimension,
    DimensionLayer,
    HistoryEntry,
    STANDARD_DIMENSIONS,
)
from huaqi_src.config.errors import DimensionNotFoundError, DimensionParseError


@pytest.fixture
def telos_dir(tmp_path: Path) -> Path:
    d = tmp_path / "telos"
    d.mkdir()
    return d


@pytest.fixture
def manager(telos_dir: Path) -> TelosManager:
    return TelosManager(telos_dir=telos_dir, git_commit=False)


class TestTelosManagerInit:
    def test_init_creates_standard_dimension_files(self, manager, telos_dir):
        manager.init()
        for dim_name in STANDARD_DIMENSIONS:
            assert (telos_dir / f"{dim_name}.md").exists()

    def test_init_creates_meta_file(self, manager, telos_dir):
        manager.init()
        assert (telos_dir / "meta.md").exists()

    def test_init_creates_index_file(self, manager, telos_dir):
        manager.init()
        assert (telos_dir / "INDEX.md").exists()

    def test_init_creates_archive_dir(self, manager, telos_dir):
        manager.init()
        assert (telos_dir / "_archive").is_dir()

    def test_init_is_idempotent(self, manager, telos_dir):
        manager.init()
        manager.init()
        assert (telos_dir / "beliefs.md").exists()


class TestTelosManagerRead:
    def test_get_existing_dimension(self, manager, telos_dir):
        manager.init()
        dim = manager.get("beliefs")
        assert dim.name == "beliefs"
        assert dim.layer == DimensionLayer.CORE

    def test_get_nonexistent_raises(self, manager, telos_dir):
        manager.init()
        with pytest.raises(DimensionNotFoundError):
            manager.get("nonexistent_dim")

    def test_list_active_returns_standard_dimensions(self, manager, telos_dir):
        manager.init()
        active = manager.list_active()
        assert len(active) == len(STANDARD_DIMENSIONS)
        names = [d.name for d in active]
        for std in STANDARD_DIMENSIONS:
            assert std in names


class TestTelosManagerUpdate:
    def test_update_changes_content(self, manager, telos_dir):
        manager.init()
        entry = HistoryEntry(
            version=1,
            change="初始更新",
            trigger="测试触发",
            confidence=0.75,
            updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        manager.update("beliefs", new_content="选择比努力更重要。", history_entry=entry, confidence=0.75)
        dim = manager.get("beliefs")
        assert "选择比努力更重要" in dim.content

    def test_update_increments_update_count(self, manager, telos_dir):
        manager.init()
        entry = HistoryEntry(
            version=1,
            change="测试",
            trigger="触发",
            confidence=0.7,
            updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        manager.update("beliefs", new_content="新认知", history_entry=entry, confidence=0.7)
        dim = manager.get("beliefs")
        assert dim.update_count == 1

    def test_update_appends_history_entry(self, manager, telos_dir):
        manager.init()
        entry = HistoryEntry(
            version=1,
            change="从 A 变成 B",
            trigger="信号累积",
            confidence=0.8,
            updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        manager.update("beliefs", new_content="新认知", history_entry=entry, confidence=0.8)
        dim = manager.get("beliefs")
        assert len(dim.history) == 1
        assert dim.history[0].change == "从 A 变成 B"

    def test_update_nonexistent_raises(self, manager, telos_dir):
        manager.init()
        entry = HistoryEntry(
            version=1, change="x", trigger="x", confidence=0.5,
            updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        with pytest.raises(DimensionNotFoundError):
            manager.update("nonexistent", new_content="x", history_entry=entry, confidence=0.5)

    def test_update_syncs_index(self, manager, telos_dir):
        manager.init()
        entry = HistoryEntry(
            version=1,
            change="方向感转变",
            trigger="日记信号",
            confidence=0.85,
            updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        manager.update("beliefs", new_content="选择比努力更重要。", history_entry=entry, confidence=0.85)
        index_text = (telos_dir / "INDEX.md").read_text(encoding="utf-8")
        assert "beliefs" in index_text


class TestTelosManagerCustomDimension:
    def test_create_custom_dimension(self, manager, telos_dir):
        manager.init()
        manager.create_custom("health", layer=DimensionLayer.SURFACE, initial_content="关注身体状态")
        assert (telos_dir / "health.md").exists()

    def test_custom_dimension_appears_in_active_list(self, manager, telos_dir):
        manager.init()
        manager.create_custom("health", layer=DimensionLayer.SURFACE, initial_content="关注身体状态")
        names = [d.name for d in manager.list_active()]
        assert "health" in names

    def test_create_duplicate_custom_dimension_raises(self, manager, telos_dir):
        manager.init()
        manager.create_custom("health", layer=DimensionLayer.SURFACE, initial_content="关注")
        with pytest.raises(ValueError):
            manager.create_custom("health", layer=DimensionLayer.SURFACE, initial_content="重复")


class TestTelosManagerArchive:
    def test_archive_moves_file_to_archive_dir(self, manager, telos_dir):
        manager.init()
        manager.create_custom("health", layer=DimensionLayer.SURFACE, initial_content="关注身体")
        manager.archive("health")
        assert not (telos_dir / "health.md").exists()
        assert (telos_dir / "_archive" / "health.md").exists()

    def test_archive_removes_from_active_list(self, manager, telos_dir):
        manager.init()
        manager.create_custom("health", layer=DimensionLayer.SURFACE, initial_content="关注身体")
        manager.archive("health")
        names = [d.name for d in manager.list_active()]
        assert "health" not in names

    def test_archive_standard_dimension_raises(self, manager, telos_dir):
        manager.init()
        with pytest.raises(ValueError):
            manager.archive("beliefs")


def test_index_md_contains_content_summary(tmp_path):
    telos_dir = tmp_path / "telos"
    manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    manager.init()

    manager.update(
        "beliefs",
        new_content="选择比努力更重要，在正确方向上努力才有复利效应",
        history_entry=HistoryEntry(
            version=1, change="初始化", trigger="问卷",
            confidence=0.5, updated_at=datetime.now(timezone.utc)
        ),
        confidence=0.5,
    )

    index = (telos_dir / "INDEX.md").read_text(encoding="utf-8")
    assert "选择比努力更重要" in index


def test_create_custom_logs_to_meta(tmp_path):
    from huaqi_src.layers.growth.telos.meta import MetaManager
    telos_dir = tmp_path / "telos"
    manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    manager.init()
    meta = MetaManager(telos_dir / "meta.md")
    initial_ops = meta.list_dimension_operations()

    manager.create_custom("health", DimensionLayer.MIDDLE, "关注身体状态", meta_manager=meta)

    ops = meta.list_dimension_operations()
    assert len(ops) == len(initial_ops) + 1
    assert ops[-1].dimension == "health"
    assert ops[-1].operation == "add"


def test_archive_logs_to_meta(tmp_path):
    from huaqi_src.layers.growth.telos.meta import MetaManager
    telos_dir = tmp_path / "telos"
    manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    manager.init()
    meta = MetaManager(telos_dir / "meta.md")
    manager.create_custom("health", DimensionLayer.MIDDLE, "关注身体状态", meta_manager=meta)

    manager.archive("health", meta_manager=meta)

    ops = meta.list_dimension_operations()
    archive_ops = [o for o in ops if o.operation == "archive"]
    assert len(archive_ops) == 1
    assert archive_ops[0].dimension == "health"


def test_telos_manager_git_commit_on_update(tmp_path):
    import subprocess
    telos_dir = tmp_path / "telos"

    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)

    manager = TelosManager(telos_dir=telos_dir, git_commit=True)
    manager.init()
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True)

    manager.update(
        "beliefs",
        new_content="选择比努力更重要",
        history_entry=HistoryEntry(
            version=1, change="更新信念", trigger="日记",
            confidence=0.7, updated_at=datetime.now(timezone.utc),
        ),
        confidence=0.7,
    )

    result = subprocess.run(
        ["git", "-C", str(tmp_path), "log", "--oneline", "-5"],
        capture_output=True, text=True,
    )
    assert "beliefs" in result.stdout
