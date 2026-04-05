import datetime
from pathlib import Path
from huaqi_src.scheduler.execution_log import JobExecutionLog


def test_write_start_creates_entry(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))

    assert isinstance(entry_id, int)
    assert entry_id > 0


def test_write_result_updates_entry(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))
    log.write_result(entry_id, "success")

    assert log.has_success("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))


def test_has_success_returns_false_when_only_running(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    log.write_start("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))

    assert not log.has_success("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))


def test_has_success_returns_false_when_failed(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))
    log.write_result(entry_id, "failed", error="超时")

    assert not log.has_success("morning_brief", datetime.datetime(2026, 5, 4, 8, 0))


def test_get_latest_returns_entries_in_range(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    since = datetime.datetime(2026, 5, 1, 0, 0)
    until = datetime.datetime(2026, 5, 4, 23, 59)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 3, 8, 0))
    log.write_result(entry_id, "success")

    results = log.get_latest("morning_brief", since, until)
    assert len(results) == 1
    assert results[0].job_id == "morning_brief"
    assert results[0].status == "success"


def test_get_latest_excludes_out_of_range(tmp_path):
    db_path = tmp_path / "scheduler.db"
    log = JobExecutionLog(db_path)

    since = datetime.datetime(2026, 5, 4, 0, 0)
    until = datetime.datetime(2026, 5, 4, 23, 59)

    entry_id = log.write_start("morning_brief", datetime.datetime(2026, 5, 1, 8, 0))
    log.write_result(entry_id, "success")

    results = log.get_latest("morning_brief", since, until)
    assert len(results) == 0
