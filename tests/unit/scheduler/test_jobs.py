from unittest.mock import patch, MagicMock
from huaqi_src.scheduler.jobs import register_default_jobs


def test_register_default_jobs_adds_morning_brief():
    mock_manager = MagicMock()
    mock_manager.add_cron_job.return_value = True

    register_default_jobs(mock_manager)

    mock_manager.add_cron_job.assert_called()
    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "morning_brief" in call_ids


def test_register_default_jobs_includes_new_reports():
    from huaqi_src.scheduler.manager import SchedulerManager

    mock_manager = MagicMock(spec=SchedulerManager)
    register_default_jobs(mock_manager)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "morning_brief" in call_ids
    assert "daily_report" in call_ids
    assert "weekly_report" in call_ids
    assert "quarterly_report" in call_ids


def test_register_jobs_skips_disabled_job():
    from unittest.mock import MagicMock
    from huaqi_src.config.manager import AppConfig, SchedulerJobConfig
    from huaqi_src.scheduler.jobs import register_default_jobs

    mock_manager = MagicMock()
    config = AppConfig(
        scheduler_jobs={"morning_brief": SchedulerJobConfig(enabled=False)}
    )

    register_default_jobs(mock_manager, config=config)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "morning_brief" not in call_ids


def test_register_jobs_uses_custom_cron():
    from unittest.mock import MagicMock
    from huaqi_src.config.manager import AppConfig, SchedulerJobConfig
    from huaqi_src.scheduler.jobs import register_default_jobs

    mock_manager = MagicMock()
    config = AppConfig(
        scheduler_jobs={"morning_brief": SchedulerJobConfig(enabled=True, cron="0 7 * * *")}
    )

    register_default_jobs(mock_manager, config=config)

    cron_calls = {call.args[0]: call.kwargs.get("cron") for call in mock_manager.add_cron_job.call_args_list}
    assert cron_calls.get("morning_brief") == "0 7 * * *"


def test_register_jobs_uses_default_cron_when_not_configured():
    from unittest.mock import MagicMock
    from huaqi_src.config.manager import AppConfig
    from huaqi_src.scheduler.jobs import register_default_jobs

    mock_manager = MagicMock()
    config = AppConfig()

    register_default_jobs(mock_manager, config=config)

    cron_calls = {call.args[0]: call.kwargs.get("cron") for call in mock_manager.add_cron_job.call_args_list}
    assert cron_calls.get("morning_brief") == "0 8 * * *"


def test_register_jobs_includes_world_fetch():
    from unittest.mock import MagicMock
    from huaqi_src.scheduler.jobs import register_default_jobs

    mock_manager = MagicMock()
    register_default_jobs(mock_manager)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "world_fetch" in call_ids
