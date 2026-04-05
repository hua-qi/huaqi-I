import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from huaqi_src.scheduler.startup_recovery import StartupJobRecovery, load_last_opened, save_last_opened


def test_load_last_opened_returns_none_when_file_missing(tmp_path):
    result = load_last_opened(tmp_path)
    assert result is None


def test_save_and_load_last_opened(tmp_path):
    dt = datetime.datetime(2026, 5, 3, 10, 0, 0)
    save_last_opened(tmp_path, dt)
    result = load_last_opened(tmp_path)
    assert result == dt


def test_recovery_updates_last_opened(tmp_path):
    db_path = tmp_path / "scheduler.db"
    job_configs = {}

    before = datetime.datetime.now() - datetime.timedelta(days=1)
    save_last_opened(tmp_path, before)

    recovery = StartupJobRecovery(data_dir=tmp_path, db_path=db_path, job_configs=job_configs)
    recovery.run(notify_callback=None)

    after = load_last_opened(tmp_path)
    assert after > before


def test_recovery_calls_notify_when_missed_jobs(tmp_path):
    db_path = tmp_path / "scheduler.db"
    job_configs = {
        "morning_brief": {"cron": "0 8 * * *", "display_name": "晨间简报"}
    }

    since = datetime.datetime.now() - datetime.timedelta(days=2)
    save_last_opened(tmp_path, since)

    notify_mock = MagicMock()
    recovery = StartupJobRecovery(data_dir=tmp_path, db_path=db_path, job_configs=job_configs)
    recovery.run(notify_callback=notify_mock)

    notify_mock.assert_called_once()
    call_args = notify_mock.call_args[0]
    assert len(call_args) >= 1


def test_recovery_does_not_call_notify_when_no_missed_jobs(tmp_path):
    from huaqi_src.scheduler.execution_log import JobExecutionLog

    db_path = tmp_path / "scheduler.db"
    job_configs = {
        "morning_brief": {"cron": "0 8 * * *", "display_name": "晨间简报"}
    }
    log = JobExecutionLog(db_path)

    now = datetime.datetime.now()
    since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    scheduled_at = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if scheduled_at > now:
        save_last_opened(tmp_path, now + datetime.timedelta(minutes=1))
    else:
        entry_id = log.write_start("morning_brief", scheduled_at)
        log.write_result(entry_id, "success")
        save_last_opened(tmp_path, since)

    notify_mock = MagicMock()
    recovery = StartupJobRecovery(data_dir=tmp_path, db_path=db_path, job_configs=job_configs)

    if scheduled_at > now:
        recovery.run(notify_callback=notify_mock)
        notify_mock.assert_not_called()
