"""APScheduler 定时任务管理器

提供定时任务的增删改查和持久化功能
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import (
    EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED,
    JobExecutionEvent
)


class SchedulerManager:
    """定时任务管理器
    
    功能：
    - 添加/删除/暂停/恢复任务
    - 支持 cron/interval/date 触发器
    - 任务持久化到 SQLite
    - 任务执行日志
    """
    
    def __init__(
        self,
        db_path: Optional[Path] = None,
        timezone: str = "Asia/Shanghai",
    ):
        """初始化调度器
        
        Args:
            db_path: 任务持久化数据库路径
            timezone: 时区
        """
        if db_path is None:
            db_path = Path.home() / ".huaqi" / "scheduler.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.timezone = timezone
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._job_listeners: List[Callable] = []
    
    @property
    def scheduler(self) -> AsyncIOScheduler:
        """获取或创建调度器"""
        if self._scheduler is None:
            # 配置 job store
            jobstores = {
                'default': SQLAlchemyJobStore(
                    url=f'sqlite:///{self.db_path}',
                    tablename='apscheduler_jobs'
                )
            }
            
            self._scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                timezone=self.timezone,
            )
            
            # 添加事件监听
            self._scheduler.add_listener(
                self._on_job_executed,
                EVENT_JOB_EXECUTED
            )
            self._scheduler.add_listener(
                self._on_job_error,
                EVENT_JOB_ERROR | EVENT_JOB_MISSED
            )
        
        return self._scheduler
    
    def _on_job_executed(self, event: JobExecutionEvent):
        """任务执行成功回调"""
        print(f"[Scheduler] 任务执行成功: {event.job_id} at {event.scheduled_run_time}")
        for listener in self._job_listeners:
            try:
                listener('executed', event.job_id, event)
            except:
                pass
    
    def _on_job_error(self, event: JobExecutionEvent):
        """任务执行失败回调"""
        exception = getattr(event, 'exception', None)
        print(f"[Scheduler] 任务执行失败: {event.job_id}, 异常: {exception}")
        for listener in self._job_listeners:
            try:
                listener('error', event.job_id, event)
            except:
                pass
    
    def add_listener(self, callback: Callable):
        """添加任务事件监听器"""
        self._job_listeners.append(callback)
    
    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron: str,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
        replace_existing: bool = True,
    ) -> bool:
        """添加 Cron 定时任务
        
        Args:
            job_id: 任务唯一ID
            func: 执行函数
            cron: cron 表达式 (如 "0 8 * * *" 每天早上8点)
            args: 函数位置参数
            kwargs: 函数关键字参数
            replace_existing: 是否替换已存在的任务
        """
        try:
            trigger = CronTrigger.from_crontab(cron, timezone=self.timezone)
            
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                args=args,
                kwargs=kwargs or {},
                replace_existing=replace_existing,
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
        """添加间隔任务
        
        Args:
            job_id: 任务ID
            func: 执行函数
            seconds/minutes/hours: 间隔时间
        """
        try:
            trigger = IntervalTrigger(
                seconds=seconds,
                minutes=minutes,
                hours=hours,
            )
            
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                args=args,
                kwargs=kwargs or {},
                replace_existing=replace_existing,
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
        """添加一次性任务
        
        Args:
            job_id: 任务ID
            func: 执行函数
            run_date: 执行时间
        """
        try:
            trigger = DateTrigger(run_date=run_date)
            
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                args=args,
                kwargs=kwargs or {},
            )
            return True
        except Exception as e:
            print(f"添加定时任务失败: {e}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """删除任务"""
        try:
            self.scheduler.remove_job(job_id)
            return True
        except Exception as e:
            print(f"删除任务失败: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """暂停任务"""
        try:
            self.scheduler.pause_job(job_id)
            return True
        except Exception as e:
            print(f"暂停任务失败: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """恢复任务"""
        try:
            self.scheduler.resume_job(job_id)
            return True
        except Exception as e:
            print(f"恢复任务失败: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """获取任务信息"""
        try:
            job = self.scheduler.get_job(job_id)
            if job is None:
                return None
            
            return {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time,
                "trigger": str(job.trigger),
            }
        except Exception as e:
            print(f"获取任务失败: {e}")
            return None
    
    def list_jobs(self) -> List[Dict]:
        """列出所有任务"""
        try:
            jobs = self.scheduler.get_jobs()
            return [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time,
                    "trigger": str(job.trigger),
                }
                for job in jobs
            ]
        except Exception as e:
            print(f"列出任务失败: {e}")
            return []
    
    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            print(f"[Scheduler] 调度器已启动，时区: {self.timezone}")
    
    def shutdown(self, wait: bool = True):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            print("[Scheduler] 调度器已关闭")
    
    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self.scheduler.running


# 单例
_scheduler_manager: Optional[SchedulerManager] = None


def get_scheduler_manager() -> SchedulerManager:
    """获取调度器管理器单例"""
    global _scheduler_manager
    if _scheduler_manager is None:
        _scheduler_manager = SchedulerManager()
    return _scheduler_manager
