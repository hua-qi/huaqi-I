from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.growth_events import GrowthEventStore
from huaqi_src.layers.growth.telos.engine import TelosEngine, Step1Output, SignalStrength


def make_pipeline(tmp_path: Path, days_window: int = 30):
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    store = RawSignalStore(adapter=adapter)
    telos_dir = tmp_path / "telos"
    telos_manager = TelosManager(telos_dir=telos_dir, git_commit=False)
    telos_manager.init()
    event_store = GrowthEventStore(adapter=adapter)
    mock_llm = MagicMock()
    engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
    return DistillationPipeline(
        signal_store=store,
        event_store=event_store,
        telos_manager=telos_manager,
        engine=engine,
        signal_threshold=2,
        days_window=days_window,
    ), store


async def test_pipeline_step2_only_queries_within_days_window(tmp_path):
    pipeline, store = make_pipeline(tmp_path, days_window=7)

    now = datetime.now(timezone.utc)
    old_signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=now - timedelta(days=10),
        content="很久以前的日记",
    )
    store.save(old_signal)
    store.mark_processed(old_signal.id)

    new_signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=now - timedelta(days=1),
        content="今天的日记",
    )
    store.save(new_signal)

    mock_llm = pipeline._engine._llm
    mock_llm.invoke.return_value = MagicMock(
        content='{"dimensions":["goals"],"emotion":"positive","intensity":0.6,"signal_strength":"medium","strong_reason":null,"summary":"今天的日记","new_dimension_hint":null}'
    )

    result = await pipeline.process(new_signal)
    assert result["pipeline_runs"] == []


async def test_pipeline_strong_signal_bypasses_threshold(tmp_path):
    import json
    pipeline, store = make_pipeline(tmp_path, days_window=30)
    now = datetime.now(timezone.utc)
    signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=now,
        content="我彻底改变了对人生的看法，这是一个重大转折点",
    )
    store.save(signal)

    step1_response = '{"dimensions":["beliefs"],"emotion":"positive","intensity":0.95,"signal_strength":"strong","strong_reason":"用户明确表达了根本性转变","summary":"人生观转变","new_dimension_hint":null,"has_people":false,"mentioned_names":[]}'
    combined_response = json.dumps({
        "should_update": True,
        "new_content": "我的人生观发生了根本性转变",
        "consistency_score": 0.9,
        "history_entry": {"change": "根本性转变", "trigger": "重大认知"},
        "is_growth_event": False,
        "growth_title": None,
        "growth_narrative": None,
    })

    mock_llm = pipeline._engine._llm
    mock_llm.invoke.return_value = MagicMock(content=step1_response)
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=combined_response))

    result = await pipeline.process(signal)
    assert len(result["pipeline_runs"]) > 0


@pytest.fixture
def signal_store(tmp_path: Path) -> RawSignalStore:
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    return RawSignalStore(adapter=adapter)


@pytest.fixture
def event_store(tmp_path: Path) -> GrowthEventStore:
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    return GrowthEventStore(adapter=adapter)


@pytest.fixture
def telos_manager(tmp_path: Path) -> TelosManager:
    telos_dir = tmp_path / "telos"
    mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
    mgr.init()
    return mgr


class TestDistillationPipelineCombinedStep:
    async def test_pipeline_uses_step345_combined_not_separate(self, signal_store, event_store, telos_manager):
        import json
        from unittest.mock import AsyncMock, MagicMock
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
        from huaqi_src.layers.growth.telos.engine import TelosEngine, Step1Output, CombinedStepOutput
        from datetime import datetime, timezone

        mock_llm = MagicMock()
        step1_data = {
            "dimensions": ["challenges", "goals"],
            "emotion": "negative",
            "intensity": 0.8,
            "signal_strength": "strong",
            "strong_reason": "强信号",
            "summary": "测试",
            "new_dimension_hint": None,
        }
        combined_data = {
            "should_update": True,
            "new_content": "新内容",
            "consistency_score": 0.8,
            "history_entry": {"change": "变化", "trigger": "触发"},
            "is_growth_event": False,
            "growth_title": None,
            "growth_narrative": None,
        }
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(step1_data))
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps(combined_data)))

        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
        pipeline = DistillationPipeline(
            signal_store=signal_store,
            event_store=event_store,
            telos_manager=telos_manager,
            engine=engine,
        )
        signal = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="测试信号",
        )
        result = await pipeline.process(signal)
        assert result["signal_id"] == signal.id
        assert len(result["pipeline_runs"]) > 0


class TestPeoplePipelineFork:
    async def test_pipeline_calls_person_extractor_when_has_people(self, signal_store, event_store, telos_manager):
        import json
        from unittest.mock import AsyncMock, MagicMock
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
        from huaqi_src.layers.growth.telos.engine import TelosEngine
        from datetime import datetime, timezone

        mock_llm = MagicMock()
        step1_data = {
            "dimensions": ["goals"],
            "emotion": "positive",
            "intensity": 0.6,
            "signal_strength": "strong",
            "strong_reason": "强信号",
            "summary": "提到了老李",
            "new_dimension_hint": None,
            "has_people": True,
            "mentioned_names": ["老李"],
        }
        combined_data = {
            "should_update": False,
            "new_content": None,
            "consistency_score": 0.3,
            "history_entry": None,
            "is_growth_event": False,
            "growth_title": None,
            "growth_narrative": None,
        }
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(step1_data))
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps(combined_data)))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        mock_extractor = MagicMock()
        mock_extractor.extract_from_text.return_value = []

        from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
        pipeline = DistillationPipeline(
            signal_store=signal_store,
            event_store=event_store,
            telos_manager=telos_manager,
            engine=engine,
            person_extractor=mock_extractor,
        )
        signal = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="今天和老李聊了很多",
        )
        await pipeline.process(signal)
        mock_extractor.extract_from_text.assert_called_once_with(signal.content)


class TestDimensionFailureIsolation:
    async def test_one_dimension_failure_does_not_block_others(self, signal_store, event_store, telos_manager):
        import json
        from unittest.mock import AsyncMock, MagicMock
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
        from huaqi_src.layers.growth.telos.engine import TelosEngine
        from datetime import datetime, timezone

        mock_llm = MagicMock()
        step1_data = {
            "dimensions": ["challenges", "goals"],
            "emotion": "negative",
            "intensity": 0.9,
            "signal_strength": "strong",
            "strong_reason": "强信号",
            "summary": "测试",
            "new_dimension_hint": None,
        }
        good_combined = json.dumps({
            "should_update": True,
            "new_content": "新内容",
            "consistency_score": 0.8,
            "history_entry": {"change": "变化", "trigger": "触发"},
            "is_growth_event": False,
            "growth_title": None,
            "growth_narrative": None,
        })

        call_count = 0

        async def ainvoke_side_effect(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("模拟维度失败")
            return MagicMock(content=good_combined)

        mock_llm.invoke.return_value = MagicMock(content=json.dumps(step1_data))
        mock_llm.ainvoke = AsyncMock(side_effect=ainvoke_side_effect)

        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
        pipeline = DistillationPipeline(
            signal_store=signal_store,
            event_store=event_store,
            telos_manager=telos_manager,
            engine=engine,
        )
        signal = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="测试信号",
        )
        result = await pipeline.process(signal)
        assert len(result["pipeline_runs"]) == 1


class TestPeopleParallelWithDimensions:
    async def test_people_pipeline_runs_parallel_with_dimensions(self, signal_store, event_store, telos_manager):
        import json
        from unittest.mock import AsyncMock, MagicMock, call
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
        from huaqi_src.layers.growth.telos.engine import TelosEngine
        from datetime import datetime, timezone

        execution_order = []

        mock_llm = MagicMock()
        step1_data = {
            "dimensions": ["challenges"],
            "emotion": "positive",
            "intensity": 0.8,
            "signal_strength": "strong",
            "strong_reason": "强",
            "summary": "测试",
            "new_dimension_hint": None,
            "has_people": True,
            "mentioned_names": ["张伟"],
        }
        combined_data = json.dumps({
            "should_update": False,
            "new_content": None,
            "consistency_score": 0.3,
            "history_entry": None,
            "is_growth_event": False,
            "growth_title": None,
            "growth_narrative": None,
        })
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(step1_data))
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=combined_data))

        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        mock_people_pipeline = MagicMock()
        mock_people_pipeline.process = AsyncMock(return_value=[])

        from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
        pipeline = DistillationPipeline(
            signal_store=signal_store,
            event_store=event_store,
            telos_manager=telos_manager,
            engine=engine,
            people_pipeline=mock_people_pipeline,
        )
        signal = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="今天和张伟讨论了挑战",
        )
        result = await pipeline.process(signal)
        mock_people_pipeline.process.assert_called_once()
        assert result["signal_id"] == signal.id


async def test_pipeline_creates_dimension_from_new_dimension_hint(tmp_path):
    import json
    pipeline, store = make_pipeline(tmp_path)
    now = datetime.now(timezone.utc)

    signal = RawSignal(
        user_id="u1",
        source_type=SourceType.WORK_DOC,
        timestamp=now,
        content="我有很强的项目管理能力",
    )
    store.save(signal)

    step1_response = json.dumps({
        "dimensions": ["goals"],
        "emotion": "positive",
        "intensity": 0.7,
        "signal_strength": "strong",
        "strong_reason": "工作技能",
        "summary": "项目管理能力",
        "new_dimension_hint": "project_management",
        "has_people": False,
        "mentioned_names": [],
    })
    combined_response = json.dumps({
        "should_update": False,
        "new_content": None,
        "consistency_score": 0.3,
        "history_entry": None,
        "is_growth_event": False,
        "growth_title": None,
        "growth_narrative": None,
    })

    mock_llm = pipeline._engine._llm
    mock_llm.invoke.return_value = MagicMock(content=step1_response)
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=combined_response))

    await pipeline.process(signal)

    from huaqi_src.config.errors import DimensionNotFoundError
    try:
        pipeline._mgr.get("project_management")
        dimension_created = True
    except DimensionNotFoundError:
        dimension_created = False
    assert dimension_created
