import datetime
import json
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

from huaqi_src.scheduler.missed_job_scanner import MissedJob, MissedJobScanner
from huaqi_src.scheduler.scheduled_job_store import ScheduledJob


_META_FILE = "scheduler_meta.json"


def load_last_opened(data_dir: Path) -> Optional[datetime.datetime]:
    meta_path = Path(data_dir) / _META_FILE
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        raw = data.get("cli_last_opened")
        if raw:
            return datetime.datetime.fromisoformat(raw)
    except Exception:
        pass
    return None


def save_last_opened(data_dir: Path, dt: datetime.datetime):
    meta_path = Path(data_dir) / _META_FILE
    existing: dict = {}
    if meta_path.exists():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["cli_last_opened"] = dt.isoformat()
    meta_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


class StartupJobRecovery:
    def __init__(
        self,
        data_dir: Path,
        db_path: Path,
        job_configs: Dict[str, dict],
        timezone: str = "Asia/Shanghai",
    ):
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.job_configs = job_configs
        self.timezone = timezone

    def run(self, notify_callback: Optional[Callable[[List[MissedJob]], None]]):
        now = datetime.datetime.now()
        last_opened = load_last_opened(self.data_dir)
        save_last_opened(self.data_dir, now)

        if last_opened is None:
            return

        if now < last_opened:
            print(
                f"[Scheduler] 检测到系统时钟回拨 (last={last_opened.isoformat()}, now={now.isoformat()})，"
                f"以保守估计重新扫描最近 24 小时"
            )
            last_opened = now - datetime.timedelta(hours=24)

        scanner = MissedJobScanner(
            db_path=self.db_path,
            job_configs=self.job_configs,
            timezone=self.timezone,
        )
        missed = scanner.scan(last_opened, now)

        if not missed:
            return

        if notify_callback is not None:
            notify_callback(missed)

        from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore
        store = ScheduledJobStore(self.data_dir)
        jobs = {job.id: job for job in store.load_jobs()}

        t = threading.Thread(
            target=self._run_missed_jobs,
            args=(missed, jobs),
            daemon=True,
        )
        t.start()

    def _run_missed_jobs(self, missed: List[MissedJob], jobs: Dict[str, ScheduledJob]):
        from huaqi_src.scheduler.execution_log import JobExecutionLog
        from huaqi_src.scheduler.job_runner import _run_scheduled_job

        log = JobExecutionLog(self.db_path)

        for missed_job in missed:
            job = jobs.get(missed_job.job_id)
            if job is None:
                continue
            entry_id = log.write_start(missed_job.job_id, missed_job.scheduled_at)
            try:
                _run_scheduled_job(
                    job.id,
                    job.prompt,
                    job.output_dir,
                    scheduled_at=missed_job.scheduled_at,
                    raise_on_error=True,
                )
                log.write_result(entry_id, "success")
            except Exception as e:
                log.write_result(entry_id, "failed", error=str(e))
