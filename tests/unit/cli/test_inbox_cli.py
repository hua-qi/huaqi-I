from typer.testing import CliRunner
from huaqi_src.cli import app

runner = CliRunner()

def test_inbox_status_shows_inbox_path(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    result = runner.invoke(app, ["inbox", "status"])
    assert result.exit_code == 0
    assert "inbox" in result.output.lower()

def test_inbox_sync_with_empty_inbox(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    result = runner.invoke(app, ["inbox", "sync"])
    assert result.exit_code == 0
    assert "0" in result.output or "没有" in result.output or "处理" in result.output
