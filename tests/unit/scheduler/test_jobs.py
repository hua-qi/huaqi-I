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

