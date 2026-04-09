from unittest.mock import MagicMock
from huaqi_src.scheduler.jobs import register_jobs
from huaqi_src.scheduler.scheduled_job_store import ScheduledJob, ScheduledJobStore


def _make_store(jobs):
    store = MagicMock(spec=ScheduledJobStore)
    store.load_jobs.return_value = jobs
    return store


def _default_jobs():
    from huaqi_src.scheduler.scheduled_job_store import _DEFAULT_JOBS
    return [ScheduledJob(**j) for j in _DEFAULT_JOBS]


def test_register_jobs_adds_morning_brief():
    mock_manager = MagicMock()
    mock_manager.scheduler.get_jobs.return_value = []
    store = _make_store(_default_jobs())

    register_jobs(mock_manager, store)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "morning_brief" in call_ids


def test_register_jobs_includes_all_default_jobs():
    mock_manager = MagicMock()
    mock_manager.scheduler.get_jobs.return_value = []
    store = _make_store(_default_jobs())

    register_jobs(mock_manager, store)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "morning_brief" in call_ids
    assert "daily_report" in call_ids
    assert "weekly_report" in call_ids
    assert "quarterly_report" in call_ids
    assert "world_fetch" in call_ids


def test_register_jobs_skips_disabled_job():
    mock_manager = MagicMock()
    mock_manager.scheduler.get_jobs.return_value = []
    jobs = [
        j.model_copy(update={"enabled": False}) if j.id == "morning_brief" else j
        for j in _default_jobs()
    ]
    store = _make_store(jobs)

    register_jobs(mock_manager, store)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "morning_brief" not in call_ids


def test_register_jobs_uses_custom_cron():
    mock_manager = MagicMock()
    mock_manager.scheduler.get_jobs.return_value = []
    jobs = [
        j.model_copy(update={"cron": "0 7 * * *"}) if j.id == "morning_brief" else j
        for j in _default_jobs()
    ]
    store = _make_store(jobs)

    register_jobs(mock_manager, store)

    cron_calls = {
        call.args[0]: call.kwargs.get("cron")
        for call in mock_manager.add_cron_job.call_args_list
    }
    assert cron_calls.get("morning_brief") == "0 7 * * *"


def test_register_jobs_includes_world_fetch():
    mock_manager = MagicMock()
    mock_manager.scheduler.get_jobs.return_value = []
    store = _make_store(_default_jobs())

    register_jobs(mock_manager, store)

    call_ids = [call.args[0] for call in mock_manager.add_cron_job.call_args_list]
    assert "world_fetch" in call_ids
