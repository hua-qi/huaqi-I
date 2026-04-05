import datetime
import json
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

from huaqi_src.scheduler.missed_job_scanner import MissedJob, MissedJobScanner


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

        t = threading.Thread(
            target=self._run_missed_jobs,
            args=(missed,),
            daemon=True,
        )
        t.start()

    def _run_missed_jobs(self, missed: List[MissedJob]):
        from huaqi_src.scheduler.execution_log import JobExecutionLog
        log = JobExecutionLog(self.db_path)

        _job_funcs = self._get_job_funcs()
        for missed_job in missed:
            func = _job_funcs.get(missed_job.job_id)
            if func is None:
                continue
            entry_id = log.write_start(missed_job.job_id, missed_job.scheduled_at)
            try:
                func()
                log.write_result(entry_id, "success")
            except Exception as e:
                log.write_result(entry_id, "failed", error=str(e))

    def _get_job_funcs(self) -> dict:
        from huaqi_src.scheduler.jobs import _JOB_FUNCS
        return _JOB_FUNCS
