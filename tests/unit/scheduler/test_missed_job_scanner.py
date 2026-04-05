import datetime
from unittest.mock import MagicMock, patch
from huaqi_src.scheduler.missed_job_scanner import MissedJobScanner, MissedJob

JOB_CONFIGS = {
    "morning_brief": {
        "cron": "0 8 * * *",
        "display_name": "晨间简报",
    }
}


def test_scanner_returns_missed_job_when_no_log(tmp_path):
    db_path = tmp_path / "scheduler.db"

    since = datetime.datetime(2026, 5, 3, 0, 0)
    until = datetime.datetime(2026, 5, 4, 9, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since, until)

    assert len(missed) >= 1
    assert any(m.job_id == "morning_brief" for m in missed)
    assert all(isinstance(m, MissedJob) for m in missed)


def test_scanner_skips_job_with_success_log(tmp_path):
    from huaqi_src.scheduler.execution_log import JobExecutionLog

    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    scheduled_at = datetime.datetime(2026, 5, 4, 8, 0)
    entry_id = log.write_start("morning_brief", scheduled_at)
    log.write_result(entry_id, "success")

    since = datetime.datetime(2026, 5, 4, 0, 0)
    until = datetime.datetime(2026, 5, 4, 9, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since, until)

    assert not any(
        m.job_id == "morning_brief" and m.scheduled_at == scheduled_at
        for m in missed
    )


def test_scanner_includes_failed_job_as_missed(tmp_path):
    from huaqi_src.scheduler.execution_log import JobExecutionLog

    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    scheduled_at = datetime.datetime(2026, 5, 4, 8, 0)
    entry_id = log.write_start("morning_brief", scheduled_at)
    log.write_result(entry_id, "failed", error="超时")

    since = datetime.datetime(2026, 5, 4, 0, 0)
    until = datetime.datetime(2026, 5, 4, 9, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since, until)

    assert any(
        m.job_id == "morning_brief" and m.scheduled_at == scheduled_at
        for m in missed
    )


def test_scanner_returns_empty_when_since_equals_until(tmp_path):
    db_path = tmp_path / "scheduler.db"
    now = datetime.datetime(2026, 5, 4, 12, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since=now, until=now)

    assert missed == []


def test_missed_job_has_correct_fields(tmp_path):
    db_path = tmp_path / "scheduler.db"
    since = datetime.datetime(2026, 5, 4, 0, 0)
    until = datetime.datetime(2026, 5, 4, 9, 0)

    scanner = MissedJobScanner(db_path=db_path, job_configs=JOB_CONFIGS)
    missed = scanner.scan(since, until)

    for m in missed:
        assert hasattr(m, "job_id")
        assert hasattr(m, "scheduled_at")
        assert hasattr(m, "display_name")
        assert isinstance(m.scheduled_at, datetime.datetime)
