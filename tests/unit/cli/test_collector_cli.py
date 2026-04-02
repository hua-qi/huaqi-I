import os
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

runner = CliRunner()


def _get_app():
    from huaqi_src.cli.__init__ import app
    return app


def test_collector_status_exits_ok(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    app = _get_app()
    result = runner.invoke(app, ["collector", "status"])
    assert result.exit_code == 0


def test_collector_sync_cli_calls_watcher(tmp_path):
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    app = _get_app()
    with patch("huaqi_src.cli.commands.collector.CLIChatWatcher") as mock_cls:
        mock_watcher = MagicMock()
        mock_watcher.sync_all.return_value = []
        mock_cls.return_value = mock_watcher
        result = runner.invoke(app, ["collector", "sync-cli"])
    assert result.exit_code == 0
