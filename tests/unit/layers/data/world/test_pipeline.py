import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from huaqi_src.layers.data.world.pipeline import WorldPipeline


def test_world_pipeline_run_saves_docs(tmp_path):
    mock_doc = MagicMock()
    mock_doc.doc_type = "world_news"

    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage") as MockStorage:
        MockFetcher.return_value.fetch_all.return_value = [mock_doc]

        pipeline = WorldPipeline(data_dir=tmp_path)
        pipeline.run()

        MockFetcher.return_value.fetch_all.assert_called_once()
        MockStorage.return_value.save.assert_called_once()


def test_world_pipeline_run_with_custom_date(tmp_path):
    target_date = datetime.date(2026, 1, 1)
    mock_doc = MagicMock()

    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage") as MockStorage:
        MockFetcher.return_value.fetch_all.return_value = [mock_doc]

        pipeline = WorldPipeline(data_dir=tmp_path)
        pipeline.run(date=target_date)

        _, call_kwargs = MockStorage.return_value.save.call_args
        assert call_kwargs.get("date") == target_date or \
               MockStorage.return_value.save.call_args[0][1] == target_date


def test_world_pipeline_run_returns_false_when_no_docs(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage"):
        MockFetcher.return_value.fetch_all.return_value = []

        pipeline = WorldPipeline(data_dir=tmp_path)
        result = pipeline.run()

        assert result is False


def test_world_pipeline_run_returns_true_on_success(tmp_path):
    mock_doc = MagicMock()

    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage"):
        MockFetcher.return_value.fetch_all.return_value = [mock_doc]

        pipeline = WorldPipeline(data_dir=tmp_path)
        result = pipeline.run()

        assert result is True


def test_world_pipeline_run_returns_false_on_exception(tmp_path):
    with patch("huaqi_src.layers.data.world.pipeline.WorldNewsFetcher") as MockFetcher, \
         patch("huaqi_src.layers.data.world.pipeline.WorldNewsStorage"):
        MockFetcher.return_value.fetch_all.side_effect = RuntimeError("网络错误")

        pipeline = WorldPipeline(data_dir=tmp_path)
        result = pipeline.run()

        assert result is False
