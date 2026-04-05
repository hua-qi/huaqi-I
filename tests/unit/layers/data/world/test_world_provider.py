import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from huaqi_src.layers.capabilities.reports.providers.world import WorldProvider
from huaqi_src.layers.capabilities.reports.providers import DateRange


def _make_date_range(date_str: str):
    d = datetime.date.fromisoformat(date_str)
    return DateRange(start=d, end=d)


def test_world_provider_returns_content_when_file_exists(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "2026-05-04.md").write_text("# 世界新闻\n测试内容", encoding="utf-8")

    provider = WorldProvider(data_dir=tmp_path)
    result = provider.get_context("morning", _make_date_range("2026-05-04"))

    assert result is not None
    assert "世界热点" in result or "世界新闻" in result or "测试内容" in result


def test_world_provider_triggers_lazy_fetch_when_file_missing(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = True
        (tmp_path / "world").mkdir()
        (tmp_path / "world" / "2026-05-04.md").write_text("lazy 采集内容", encoding="utf-8")

        provider = WorldProvider(data_dir=tmp_path)

        world_file = tmp_path / "world" / "2026-05-04.md"
        world_file.unlink()

        def fake_run(**kwargs):
            world_file.write_text("lazy 采集内容", encoding="utf-8")
            return True

        MockPipeline.return_value.run.side_effect = fake_run
        result = provider.get_context("morning", _make_date_range("2026-05-04"))

        MockPipeline.return_value.run.assert_called_once()
        assert result is not None


def test_world_provider_returns_none_when_lazy_fetch_fails(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = False

        provider = WorldProvider(data_dir=tmp_path)
        result = provider.get_context("morning", _make_date_range("2026-05-04"))

        assert result is None


def test_world_provider_returns_none_when_lazy_fetch_raises(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.side_effect = RuntimeError("网络错误")

        provider = WorldProvider(data_dir=tmp_path)
        result = provider.get_context("morning", _make_date_range("2026-05-04"))

        assert result is None
