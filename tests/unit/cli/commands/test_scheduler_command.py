from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from huaqi_src.cli.commands.scheduler import scheduler_app

runner = CliRunner()


def test_scheduler_list_command():
    with patch("huaqi_src.cli.commands.scheduler._get_config_manager") as mock_cm:
        from huaqi_src.config.manager import AppConfig
        mock_cm.return_value.load_config.return_value = AppConfig()
        result = runner.invoke(scheduler_app, ["list"])
        assert result.exit_code == 0


def test_scheduler_enable_command():
    with patch("huaqi_src.cli.commands.scheduler._get_config_manager") as mock_cm:
        from huaqi_src.config.manager import AppConfig, SchedulerJobConfig
        config = AppConfig()
        mock_cm.return_value.load_config.return_value = config
        result = runner.invoke(scheduler_app, ["enable", "morning_brief"])
        assert result.exit_code == 0
        mock_cm.return_value.save_config.assert_called_once()


def test_scheduler_disable_command():
    with patch("huaqi_src.cli.commands.scheduler._get_config_manager") as mock_cm:
        from huaqi_src.config.manager import AppConfig, SchedulerJobConfig
        config = AppConfig()
        mock_cm.return_value.load_config.return_value = config
        result = runner.invoke(scheduler_app, ["disable", "morning_brief"])
        assert result.exit_code == 0
        mock_cm.return_value.save_config.assert_called_once()


def test_scheduler_set_cron_command():
    with patch("huaqi_src.cli.commands.scheduler._get_config_manager") as mock_cm:
        from huaqi_src.config.manager import AppConfig
        config = AppConfig()
        mock_cm.return_value.load_config.return_value = config
        result = runner.invoke(scheduler_app, ["set-cron", "morning_brief", "0 7 * * *"])
        assert result.exit_code == 0
        mock_cm.return_value.save_config.assert_called_once()
