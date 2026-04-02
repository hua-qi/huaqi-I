from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock
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


def test_pipeline_step2_only_queries_within_days_window(tmp_path):
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

    result = pipeline.process(new_signal)
    assert result["pipeline_runs"] == []


def test_pipeline_strong_signal_bypasses_threshold(tmp_path):
    pipeline, store = make_pipeline(tmp_path, days_window=30)
    now = datetime.now(timezone.utc)
    signal = RawSignal(
        user_id="u1",
        source_type=SourceType.JOURNAL,
        timestamp=now,
        content="我彻底改变了对人生的看法，这是一个重大转折点",
    )
    store.save(signal)

    mock_llm = pipeline._engine._llm
    mock_llm.invoke.return_value = MagicMock(
        content='{"dimensions":["beliefs"],"emotion":"positive","intensity":0.95,"signal_strength":"strong","strong_reason":"用户明确表达了根本性转变","summary":"人生观转变","new_dimension_hint":null}'
    )

    result = pipeline.process(signal)
    assert len(result["pipeline_runs"]) > 0
