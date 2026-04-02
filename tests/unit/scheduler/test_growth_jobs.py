import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from pathlib import Path

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
from huaqi_src.scheduler.jobs import process_pending_signals_job


def test_process_pending_signals_job_calls_pipeline(tmp_path):
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    store = RawSignalStore(adapter=adapter)

    for i in range(3):
        store.save(RawSignal(
            user_id="u1",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content=f"待处理信号 {i}",
        ))

    mock_pipeline = MagicMock()
    process_pending_signals_job(signal_store=store, pipeline=mock_pipeline, user_id="u1", batch_size=10)
    assert mock_pipeline.process.call_count == 3


def test_process_pending_signals_job_skips_processed(tmp_path):
    adapter = SQLiteStorageAdapter(db_path=tmp_path / "test.db")
    store = RawSignalStore(adapter=adapter)

    signal = RawSignal(
        user_id="u1", source_type=SourceType.JOURNAL,
        timestamp=datetime.now(timezone.utc), content="已处理信号",
    )
    store.save(signal)
    store.mark_processed(signal.id)

    mock_pipeline = MagicMock()
    process_pending_signals_job(signal_store=store, pipeline=mock_pipeline, user_id="u1", batch_size=10)
    mock_pipeline.process.assert_not_called()
