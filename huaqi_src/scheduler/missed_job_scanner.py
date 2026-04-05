import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from apscheduler.triggers.cron import CronTrigger

from huaqi_src.scheduler.execution_log import JobExecutionLog


@dataclass
class MissedJob:
    job_id: str
    scheduled_at: datetime.datetime
    display_name: str


class MissedJobScanner:
    def __init__(
        self,
        db_path: Path,
        job_configs: Dict[str, dict],
        timezone: str = "Asia/Shanghai",
    ):
        self.log = JobExecutionLog(db_path)
        self.job_configs = job_configs
        self.timezone = timezone

    def scan(self, since: datetime.datetime, until: datetime.datetime) -> List[MissedJob]:
        if since >= until:
            return []

        missed: List[MissedJob] = []
        for job_id, config in self.job_configs.items():
            cron = config.get("cron", "")
            display_name = config.get("display_name", job_id)
            if not cron:
                continue
            fire_times = self._get_fire_times(cron, since, until)
            for fire_time in fire_times:
                if not self.log.has_success(job_id, fire_time):
                    missed.append(MissedJob(
                        job_id=job_id,
                        scheduled_at=fire_time,
                        display_name=display_name,
                    ))
        return missed

    def _get_fire_times(
        self,
        cron: str,
        since: datetime.datetime,
        until: datetime.datetime,
    ) -> List[datetime.datetime]:
        trigger = CronTrigger.from_crontab(cron, timezone=self.timezone)
        fire_times = []
        current = since
        while True:
            next_time = trigger.get_next_fire_time(None, current)
            if next_time is None:
                break
            next_naive = next_time.replace(tzinfo=None) if next_time.tzinfo else next_time
            if next_naive > until:
                break
            fire_times.append(next_naive)
            current = next_naive + datetime.timedelta(seconds=1)
        return fire_times
