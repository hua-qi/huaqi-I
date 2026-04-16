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


class TestDistillationJob:
    def test_run_processes_unprocessed_signals(self, tmp_path):
        from huaqi_src.scheduler.distillation_job import run_distillation_job
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(return_value={"signal_id": "s1", "pipeline_runs": []})

        mock_store = MagicMock()
        from datetime import datetime, timezone
        from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
        fake_signal = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="测试信号内容",
        )
        mock_store.query.return_value = [fake_signal]

        with patch("huaqi_src.scheduler.distillation_job._get_pipeline", return_value=mock_pipeline):
            with patch("huaqi_src.scheduler.distillation_job._get_signal_store", return_value=mock_store):
                result = run_distillation_job(limit=10)

        assert result["processed"] == 1
        mock_pipeline.process.assert_called_once_with(fake_signal)

    def test_run_returns_zero_when_no_unprocessed(self, tmp_path):
        from huaqi_src.scheduler.distillation_job import run_distillation_job
        from unittest.mock import MagicMock, patch

        mock_pipeline = MagicMock()
        mock_store = MagicMock()
        mock_store.query.return_value = []

        with patch("huaqi_src.scheduler.distillation_job._get_pipeline", return_value=mock_pipeline):
            with patch("huaqi_src.scheduler.distillation_job._get_signal_store", return_value=mock_store):
                result = run_distillation_job(limit=10)

        assert result["processed"] == 0
        mock_pipeline.process.assert_not_called()


class TestReviewJob:
    def test_review_job_calls_engine_for_stale_dimensions(self, tmp_path):
        from huaqi_src.scheduler.review_job import run_review_job
        from unittest.mock import MagicMock, patch
        from datetime import datetime, timezone, timedelta

        mock_engine = MagicMock()
        mock_engine.review_stale_dimension.return_value = MagicMock(is_stale=False)

        mock_mgr = MagicMock()
        from huaqi_src.layers.growth.telos.models import DimensionLayer
        from huaqi_src.layers.growth.telos.models import TelosDimension
        stale_dim = TelosDimension(
            name="beliefs",
            layer=DimensionLayer.CORE,
            content="当前内容",
            confidence=0.8,
        )
        mock_mgr.list_active.return_value = [stale_dim]

        stale_date = datetime.now(timezone.utc) - timedelta(days=35)

        with patch("huaqi_src.scheduler.review_job._get_engine_and_manager", return_value=(mock_engine, mock_mgr)):
            with patch("huaqi_src.scheduler.review_job._get_dimension_last_updated", return_value=stale_date):
                result = run_review_job(stale_threshold_days=30)

        assert result["reviewed"] >= 1
        mock_engine.review_stale_dimension.assert_called()
