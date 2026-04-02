import pytest
from datetime import datetime, timezone
from pathlib import Path

from huaqi_src.layers.growth.telos.meta import MetaManager, CorrectionRecord, DimensionOperation


@pytest.fixture
def meta_path(tmp_path: Path) -> Path:
    return tmp_path / "telos" / "meta.md"


@pytest.fixture
def manager(meta_path: Path) -> MetaManager:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    return MetaManager(meta_path=meta_path)


class TestMetaManagerInit:
    def test_init_creates_meta_file(self, manager, meta_path):
        manager.init(active_dimensions=["beliefs", "goals"])
        assert meta_path.exists()

    def test_init_writes_active_dimensions(self, manager, meta_path):
        manager.init(active_dimensions=["beliefs", "goals", "challenges"])
        text = meta_path.read_text(encoding="utf-8")
        assert "beliefs" in text
        assert "goals" in text


class TestCorrectionRecord:
    def test_add_correction(self, manager, meta_path):
        manager.init(active_dimensions=["beliefs"])
        record = CorrectionRecord(
            date=datetime(2026, 1, 4, tzinfo=timezone.utc),
            agent_conclusion="你似乎对社交感到焦虑",
            user_feedback="不对，我只是内向",
            correction_direction="区分「内向」和「焦虑」",
        )
        manager.add_correction(record)
        text = meta_path.read_text(encoding="utf-8")
        assert "你似乎对社交感到焦虑" in text
        assert "区分「内向」和「焦虑」" in text

    def test_list_corrections(self, manager, meta_path):
        manager.init(active_dimensions=["beliefs"])
        for i in range(3):
            manager.add_correction(CorrectionRecord(
                date=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                agent_conclusion=f"结论{i}",
                user_feedback=f"反馈{i}",
                correction_direction=f"校正{i}",
            ))
        records = manager.list_corrections()
        assert len(records) == 3


class TestActiveDimensions:
    def test_get_active_dimensions(self, manager):
        manager.init(active_dimensions=["beliefs", "goals", "learned"])
        dims = manager.get_active_dimensions()
        assert set(dims) == {"beliefs", "goals", "learned"}

    def test_add_dimension_to_active(self, manager):
        manager.init(active_dimensions=["beliefs"])
        manager.add_active_dimension("health")
        dims = manager.get_active_dimensions()
        assert "health" in dims

    def test_remove_dimension_from_active(self, manager):
        manager.init(active_dimensions=["beliefs", "health"])
        manager.remove_active_dimension("health")
        dims = manager.get_active_dimensions()
        assert "health" not in dims
        assert "beliefs" in dims


class TestDimensionEvolution:
    def test_log_dimension_operation(self, manager, meta_path):
        manager.init(active_dimensions=["beliefs"])
        op = DimensionOperation(
            dimension="health",
            operation="用户创建",
            date=datetime(2026, 1, 4, tzinfo=timezone.utc),
            reason="开始关注身体状态",
        )
        manager.log_dimension_operation(op)
        text = meta_path.read_text(encoding="utf-8")
        assert "health" in text
        assert "用户创建" in text

    def test_list_dimension_operations(self, manager, meta_path):
        manager.init(active_dimensions=["beliefs"])
        manager.log_dimension_operation(DimensionOperation(
            dimension="health",
            operation="用户创建",
            date=datetime(2026, 1, 4, tzinfo=timezone.utc),
            reason="原因",
        ))
        ops = manager.list_dimension_operations()
        assert len(ops) == 1
        assert ops[0].dimension == "health"


def test_correction_reduces_dimension_confidence(tmp_path):
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.models import HistoryEntry

    telos_dir = tmp_path / "telos"
    manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    manager.init()
    manager.update(
        "beliefs",
        new_content="努力一定有回报",
        history_entry=HistoryEntry(version=1, change="初始", trigger="问卷",
                                   confidence=0.8, updated_at=datetime.now(timezone.utc)),
        confidence=0.8,
    )

    meta = MetaManager(telos_dir / "meta.md")
    meta.init(["beliefs"])

    record = CorrectionRecord(
        date=datetime.now(timezone.utc),
        agent_conclusion="努力一定有回报",
        user_feedback="不对，选择比努力更重要",
        correction_direction="修正「努力回报」信念",
    )
    meta.add_correction(record, dimension="beliefs", telos_manager=manager)

    dim = manager.get("beliefs")
    assert dim.confidence < 0.8
