from typer.testing import CliRunner
from huaqi_src.cli import app

runner = CliRunner()

def test_report_command_help():
    result = runner.invoke(app, ["report", "--help"])
    assert result.exit_code == 0
    assert "morning" in result.output
    assert "daily" in result.output
