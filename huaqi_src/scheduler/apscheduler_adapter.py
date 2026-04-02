from apscheduler.schedulers.background import BackgroundScheduler


class APSchedulerAdapter:
    def __init__(self):
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    def add_interval_job(self, func, seconds: int, job_id: str) -> None:
        self._scheduler.add_job(func, "interval", seconds=seconds, id=job_id)
