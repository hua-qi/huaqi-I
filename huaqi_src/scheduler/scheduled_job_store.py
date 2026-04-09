import contextlib
import fcntl
from pathlib import Path
from typing import List, Optional

import yaml
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, field_validator


class ScheduledJob(BaseModel):
    id: str
    display_name: str
    cron: str
    enabled: bool = True
    prompt: str
    output_dir: Optional[str] = None

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        try:
            CronTrigger.from_crontab(v)
        except Exception as e:
            raise ValueError(f"无效的 cron 表达式 '{v}': {e}") from e
        return v


_DEFAULT_JOBS: List[dict] = [
    {
        "id": "morning_brief",
        "display_name": "晨间简报",
        "cron": "0 8 * * *",
        "enabled": True,
        "prompt": "请生成今日晨间简报，总结近期重点事项、今日日程安排和值得关注的信息。",
    },
    {
        "id": "daily_report",
        "display_name": "日终复盘",
        "cron": "0 23 * * *",
        "enabled": True,
        "prompt": "请生成今日工作复盘报告，总结今天的聊天记录、完成的任务和学习内容。",
    },
    {
        "id": "weekly_report",
        "display_name": "周报",
        "cron": "0 21 * * 0",
        "enabled": True,
        "prompt": "请生成本周周报，总结本周的工作、学习和成长轨迹。",
    },
    {
        "id": "quarterly_report",
        "display_name": "季报",
        "cron": "0 22 28-31 3,6,9,12 *",
        "enabled": True,
        "prompt": "请生成本季度季报，回顾本季度的目标达成情况和成长轨迹。",
    },
    {
        "id": "learning_daily_push",
        "display_name": "学习推送",
        "cron": "0 21 * * *",
        "enabled": True,
        "prompt": "请推送今日学习内容，从进行中的课程中选取一个知识点出题复习。",
    },
    {
        "id": "world_fetch",
        "display_name": "世界新闻采集",
        "cron": "0 7 * * *",
        "enabled": True,
        "prompt": "请采集今日世界新闻并存储到本地。",
    },
]


def _serialize_jobs(jobs: List[ScheduledJob]) -> list:
    result = []
    for job in jobs:
        d = job.model_dump(exclude_none=True)
        result.append(d)
    return result


class ScheduledJobStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._path = self.data_dir / "memory" / "scheduled_jobs.yaml"

    def _ensure_initialized(self):
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._write_raw(_DEFAULT_JOBS)

    def _write_raw(self, data: list):
        tmp_path = self._path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        tmp_path.replace(self._path)

    @contextlib.contextmanager
    def _locked(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._path.with_suffix(".lock")
        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)

    def _load_raw(self) -> List[ScheduledJob]:
        with open(self._path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or []
        return [ScheduledJob(**item) for item in raw]

    def load_jobs(self) -> List[ScheduledJob]:
        self._ensure_initialized()
        return self._load_raw()

    def save_jobs(self, jobs: List[ScheduledJob]):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked():
            self._write_raw(_serialize_jobs(jobs))

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        for job in self.load_jobs():
            if job.id == job_id:
                return job
        return None

    def add_job(self, job: ScheduledJob):
        self._ensure_initialized()
        with self._locked():
            jobs = self._load_raw()
            if any(j.id == job.id for j in jobs):
                raise ValueError(f"任务 ID 已存在: {job.id}")
            jobs.append(job)
            self._write_raw(_serialize_jobs(jobs))

    def update_job(self, job: ScheduledJob):
        self._ensure_initialized()
        with self._locked():
            jobs = self._load_raw()
            for i, j in enumerate(jobs):
                if j.id == job.id:
                    jobs[i] = job
                    self._write_raw(_serialize_jobs(jobs))
                    return
            raise ValueError(f"任务不存在: {job.id}")

    def remove_job(self, job_id: str):
        self._ensure_initialized()
        with self._locked():
            jobs = self._load_raw()
            new_jobs = [j for j in jobs if j.id != job_id]
            if len(new_jobs) == len(jobs):
                raise ValueError(f"任务不存在: {job_id}")
            self._write_raw(_serialize_jobs(new_jobs))
