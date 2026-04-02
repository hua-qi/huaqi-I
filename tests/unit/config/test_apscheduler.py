import time
from huaqi_src.scheduler.apscheduler_adapter import APSchedulerAdapter


def test_apscheduler_runs_interval_job():
    results = []
    scheduler = APSchedulerAdapter()
    scheduler.start()
    scheduler.add_interval_job(lambda: results.append(1), seconds=1, job_id="test_job")
    time.sleep(2.5)
    scheduler.stop()
    assert len(results) >= 2
