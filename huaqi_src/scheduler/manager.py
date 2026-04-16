"""APScheduler 定时任务管理器（APScheduler v4）

提供定时任务的增删改查和持久化功能
"""

import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger


class SchedulerManager:
    """定时任务管理器（APScheduler v4）

    使用 AsyncScheduler.run_until_stopped() 驱动任务循环，
    运行在独立后台线程的 asyncio event loop 中。
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        timezone: str = "Asia/Shanghai",
    ):
        if db_path is None:
            from ..config.paths import get_scheduler_db_path
            db_path = get_scheduler_db_path()

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.timezone = timezone
        self._scheduler: Optional[AsyncScheduler] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._running = False

    def _make_scheduler(self) -> AsyncScheduler:
        try:
            from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
            data_store = SQLAlchemyDataStore(f"sqlite:///{self.db_path}")
            return AsyncScheduler(data_store=data_store)
        except Exception:
            return AsyncScheduler()

    def _run_in_loop(self, coro):
        if not self._running or self._loop is None:
            return None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=10)

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron: str,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
        replace_existing: bool = True,
    ) -> bool:
        try:
            trigger = CronTrigger.from_crontab(cron, timezone=self.timezone)
            from apscheduler import ConflictPolicy
            policy = ConflictPolicy.replace if replace_existing else ConflictPolicy.do_nothing
            self._run_in_loop(
                self._scheduler.add_schedule(
                    func, trigger,
                    id=job_id,
                    args=list(args),
                    kwargs=kwargs or {},
                    conflict_policy=policy,
                )
            )
            return True
        except Exception as e:
            print(f"添加定时任务失败: {e}")
            return False

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
        replace_existing: bool = True,
    ) -> bool:
        try:
            trigger = IntervalTrigger(seconds=seconds + minutes * 60 + hours * 3600)
            from apscheduler import ConflictPolicy
            policy = ConflictPolicy.replace if replace_existing else ConflictPolicy.do_nothing
            self._run_in_loop(
                self._scheduler.add_schedule(
                    func, trigger,
                    id=job_id,
                    args=list(args),
                    kwargs=kwargs or {},
                    conflict_policy=policy,
                )
            )
            return True
        except Exception as e:
            print(f"添加间隔任务失败: {e}")
            return False

    def add_date_job(
        self,
        job_id: str,
        func: Callable,
        run_date: datetime,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
    ) -> bool:
        try:
            trigger = DateTrigger(run_time=run_date)
            from apscheduler import ConflictPolicy
            self._run_in_loop(
                self._scheduler.add_schedule(
                    func, trigger,
                    id=job_id,
                    args=list(args),
                    kwargs=kwargs or {},
                    conflict_policy=ConflictPolicy.replace,
                )
            )
            return True
        except Exception as e:
            print(f"添加定时任务失败: {e}")
            return False

    def remove_job(self, job_id: str) -> bool:
        try:
            self._run_in_loop(self._scheduler.remove_schedule(job_id))
            return True
        except Exception as e:
            print(f"删除任务失败: {e}")
            return False

    def pause_job(self, job_id: str) -> bool:
        try:
            self._run_in_loop(self._scheduler.pause_schedule(job_id))
            return True
        except Exception as e:
            print(f"暂停任务失败: {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        try:
            self._run_in_loop(self._scheduler.unpause_schedule(job_id))
            return True
        except Exception as e:
            print(f"恢复任务失败: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[Dict]:
        try:
            schedule = self._run_in_loop(self._scheduler.get_schedule(job_id))
            if schedule is None:
                return None
            return {
                "id": schedule.id,
                "name": str(schedule.task_id),
                "next_run_time": schedule.next_fire_time,
                "trigger": str(schedule.trigger),
            }
        except Exception as e:
            print(f"获取任务失败: {e}")
            return None

    def list_jobs(self) -> List[Dict]:
        if not self._running or self._scheduler is None:
            return []
        try:
            schedules = self._run_in_loop(self._scheduler.get_schedules())
            return [
                {
                    "id": s.id,
                    "name": str(s.task_id),
                    "next_run_time": s.next_fire_time,
                    "trigger": str(s.trigger),
                }
                for s in (schedules or [])
            ]
        except Exception as e:
            print(f"列出任务失败: {e}")
            return []

    def start(self):
        if self._running:
            return

        self._scheduler = self._make_scheduler()
        ready_event = threading.Event()

        def _run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._async_run(ready_event))
            except Exception as e:
                print(f"[Scheduler] 调度器异常退出: {e}")
            finally:
                self._running = False

        self._thread = threading.Thread(target=_run_loop, daemon=False)
        self._thread.start()
        ready_event.wait(timeout=15)
        if not self._running:
            print("[Scheduler] 调度器启动失败")
            return
        print(f"[Scheduler] 调度器已启动，时区: {self.timezone}")

    async def _async_run(self, ready_event: threading.Event):
        self._stop_event = asyncio.Event()

        async def _wait_for_stop():
            await self._stop_event.wait()
            await self._scheduler.stop()

        self._running = True
        ready_event.set()

        asyncio.get_event_loop().create_task(_wait_for_stop())
        await self._scheduler.run_until_stopped()

    def shutdown(self, wait: bool = True):
        if not self._running or self._loop is None or self._stop_event is None:
            return
        self._loop.call_soon_threadsafe(self._stop_event.set)
        if wait and self._thread:
            self._thread.join(timeout=15)
        self._running = False
        print("[Scheduler] 调度器已关闭")

    def is_running(self) -> bool:
        return self._running


_scheduler_manager: Optional[SchedulerManager] = None


def get_scheduler_manager() -> SchedulerManager:
    global _scheduler_manager
    if _scheduler_manager is None:
        _scheduler_manager = SchedulerManager()
    return _scheduler_manager
