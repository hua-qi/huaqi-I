import datetime
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from huaqi_src.cli import app

runner = CliRunner()


def test_world_fetch_command_runs_pipeline():
    with patch("huaqi_src.cli.commands.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = True
        result = runner.invoke(app, ["world", "fetch"])
        assert result.exit_code == 0
        MockPipeline.return_value.run.assert_called_once()


def test_world_fetch_command_with_date_option():
    with patch("huaqi_src.cli.commands.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = True
        result = runner.invoke(app, ["world", "fetch", "--date", "2026-01-01"])
        assert result.exit_code == 0
        call_kwargs = MockPipeline.return_value.run.call_args
        assert datetime.date(2026, 1, 1) in (call_kwargs.args or ()) or \
               call_kwargs.kwargs.get("date") == datetime.date(2026, 1, 1)


def test_world_fetch_command_shows_error_on_failure():
    with patch("huaqi_src.cli.commands.world.WorldPipeline") as MockPipeline:
        MockPipeline.return_value.run.return_value = False
        result = runner.invoke(app, ["world", "fetch"])
        assert result.exit_code != 0 or "失败" in result.output or "未获取" in result.output
