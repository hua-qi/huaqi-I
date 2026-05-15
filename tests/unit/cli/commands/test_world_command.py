import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from huaqi_src.cli import app

runner = CliRunner()


def test_world_fetch_command_runs_pipeline():
    with patch("huaqi_src.cli.commands.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = "path/to/file.md"
        result = runner.invoke(app, ["world", "fetch"])
        assert result.exit_code == 0
        MockPipeline.return_value.run.assert_called_once()


def test_world_fetch_command_with_date_option():
    with patch("huaqi_src.cli.commands.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = "path/to/file.md"
        result = runner.invoke(app, ["world", "fetch", "--date", "2026-01-01"])
        assert result.exit_code == 0
        call_kwargs = MockPipeline.return_value.run.call_args
        assert datetime.date(2026, 1, 1) in (call_kwargs.args or ()) or \
               call_kwargs.kwargs.get("date") == datetime.date(2026, 1, 1)


def test_world_fetch_command_shows_error_on_failure():
    with patch("huaqi_src.cli.commands.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = None
        result = runner.invoke(app, ["world", "fetch"])
        assert result.exit_code != 0 or "失败" in result.output or "未获取" in result.output


class TestLoadUserContext:
    def test_returns_none_when_telos_dir_missing(self, tmp_path, monkeypatch):
        """无 TELOS 目录时返回 None。"""
        from huaqi_src.cli.commands.world import _load_user_context
        from huaqi_src.config import paths

        monkeypatch.setattr(paths, "require_data_dir", lambda: tmp_path)
        assert _load_user_context() is None

    def test_returns_content_when_telos_data_exists(self, tmp_path, monkeypatch):
        """TELOS 数据存在时返回用户画像文本。"""
        from huaqi_src.cli.commands.world import _load_user_context
        from huaqi_src.config import paths
        from huaqi_src.layers.growth.telos.models import (
            TelosDimension, DimensionLayer,
        )

        # 用 TelosDimension.to_markdown() 创建符合格式的文件
        telos_dir = tmp_path / "telos"
        telos_dir.mkdir()
        goals = TelosDimension(
            name="goals", layer=DimensionLayer.MIDDLE,
            content="正在开发一个 AI 助手产品", confidence=0.8, update_count=5,
        )
        (telos_dir / "goals.md").write_text(goals.to_markdown(), encoding="utf-8")
        challenges = TelosDimension(
            name="challenges", layer=DimensionLayer.MIDDLE,
            content="时间管理困难", confidence=0.7, update_count=3,
        )
        (telos_dir / "challenges.md").write_text(
            challenges.to_markdown(), encoding="utf-8"
        )

        monkeypatch.setattr(paths, "require_data_dir", lambda: tmp_path)
        result = _load_user_context()
        assert result is not None
        assert "AI 助手" in result
        assert "时间管理" in result


class TestFetchCmdPassesUserContext:
    def test_enricher_receives_user_context(self, tmp_path, monkeypatch):
        """enricher.enrich_file 被调用时传入了 user_context。"""
        from huaqi_src.cli.commands.world import fetch_cmd

        mock_file = tmp_path / "world" / "2026-05-15.md"
        mock_file.parent.mkdir(parents=True)
        mock_file.write_text(
            "# test\n\ncontent\n\n**链接**：https://x.com\n", encoding="utf-8"
        )

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = mock_file

        mock_enricher = MagicMock()
        mock_enricher.enrich_file.return_value = True

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with patch("huaqi_src.cli.commands.world.WorldPipeline",
                   return_value=mock_pipeline), \
             patch("huaqi_src.cli.commands.world._build_enricher",
                   return_value=mock_enricher), \
             patch("huaqi_src.cli.commands.world._load_user_context",
                   return_value="用户画像测试文本"):

            result = CliRunner().invoke(app, ["world", "fetch"])
            assert result.exit_code == 0
            call_kwargs = mock_enricher.enrich_file.call_args
            assert call_kwargs is not None
            assert call_kwargs.kwargs.get("user_context") == "用户画像测试文本"
