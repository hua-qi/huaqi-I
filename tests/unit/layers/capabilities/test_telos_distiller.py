"""Unit tests for telos_distiller module."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType


class TestRunDistillation:
    def test_returns_zero_when_no_unprocessed(self, tmp_path):
        """AC-5: 无未处理信号时返回 processed=0，不报错。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation

        mock_store = MagicMock()
        mock_store.query.return_value = []

        with patch(
            "huaqi_src.layers.capabilities.telos_distiller._get_signal_store",
            return_value=mock_store,
        ):
            result = run_distillation(limit=10, user_id="test_user")

        assert result["processed"] == 0
        assert result["errors"] == 0

    def test_processes_unprocessed_signals(self, tmp_path):
        """AC-4: 查询 processed=0 的信号并逐条送入 pipeline。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation

        signal1 = RawSignal(
            user_id="test_user",
            source_type=SourceType.AI_CHAT,
            timestamp=datetime.now(timezone.utc),
            content="测试信号1",
        )
        signal2 = RawSignal(
            user_id="test_user",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="测试信号2",
        )

        mock_store = MagicMock()
        mock_store.query.return_value = [signal1, signal2]

        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(return_value={"signal_id": "s1"})

        with patch(
            "huaqi_src.layers.capabilities.telos_distiller._get_signal_store",
            return_value=mock_store,
        ):
            with patch(
                "huaqi_src.layers.capabilities.telos_distiller._get_pipeline",
                return_value=mock_pipeline,
            ):
                result = run_distillation(limit=10, user_id="test_user")

        assert result["processed"] == 2
        assert result["errors"] == 0
        assert mock_pipeline.process.call_count == 2

    def test_error_isolation(self, tmp_path):
        """AC-6: 单条蒸馏失败不影响其余信号。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation

        signal1 = RawSignal(
            user_id="test_user",
            source_type=SourceType.AI_CHAT,
            timestamp=datetime.now(timezone.utc),
            content="正常信号",
        )
        signal2 = RawSignal(
            user_id="test_user",
            source_type=SourceType.JOURNAL,
            timestamp=datetime.now(timezone.utc),
            content="会失败的信号",
        )

        mock_store = MagicMock()
        mock_store.query.return_value = [signal1, signal2]

        mock_pipeline = MagicMock()

        async def side_effect(signal):
            if "失败" in signal.content:
                raise RuntimeError("模拟失败")
            return {"signal_id": signal.id}

        mock_pipeline.process = AsyncMock(side_effect=side_effect)

        with patch(
            "huaqi_src.layers.capabilities.telos_distiller._get_signal_store",
            return_value=mock_store,
        ):
            with patch(
                "huaqi_src.layers.capabilities.telos_distiller._get_pipeline",
                return_value=mock_pipeline,
            ):
                result = run_distillation(limit=10, user_id="test_user")

        assert result["processed"] == 1
        assert result["errors"] == 1

    def test_signals_marked_processed_after_distillation(self, tmp_path):
        """AC-7: 蒸馏完成后信号被标记为 processed=1。"""
        from huaqi_src.layers.capabilities.telos_distiller import run_distillation

        signal = RawSignal(
            user_id="test_user",
            source_type=SourceType.AI_CHAT,
            timestamp=datetime.now(timezone.utc),
            content="测试信号",
        )

        mock_store = MagicMock()
        mock_store.query.return_value = [signal]

        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(return_value={"signal_id": signal.id})

        with patch(
            "huaqi_src.layers.capabilities.telos_distiller._get_signal_store",
            return_value=mock_store,
        ):
            with patch(
                "huaqi_src.layers.capabilities.telos_distiller._get_pipeline",
                return_value=mock_pipeline,
            ):
                run_distillation(limit=10, user_id="test_user")

        mock_store.mark_processed.assert_called_once_with(signal.id)
