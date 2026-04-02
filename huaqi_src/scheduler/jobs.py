from typing import Any

from huaqi_src.layers.data.raw_signal.models import RawSignalFilter
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.scheduler.manager import SchedulerManager
from huaqi_src.config.manager import ConfigManager


def _run_morning_brief():
    from huaqi_src.layers.capabilities.reports.morning_brief import MorningBriefAgent
    try:
        agent = MorningBriefAgent()
        agent.run()
    except Exception as e:
        print(f"[MorningBrief] 生成失败: {e}")


def _run_daily_report():
    from huaqi_src.layers.capabilities.reports.daily_report import DailyReportAgent
    try:
        agent = DailyReportAgent()
        agent.run()
    except Exception as e:
        print(f"[DailyReport] 生成失败: {e}")


def _run_weekly_report():
    from huaqi_src.layers.capabilities.reports.weekly_report import WeeklyReportAgent
    try:
        agent = WeeklyReportAgent()
        agent.run()
    except Exception as e:
        print(f"[WeeklyReport] 生成失败: {e}")


def _run_quarterly_report():
    from huaqi_src.layers.capabilities.reports.quarterly_report import QuarterlyReportAgent
    try:
        agent = QuarterlyReportAgent()
        agent.run()
    except Exception as e:
        print(f"[QuarterlyReport] 生成失败: {e}")


def _get_learning_store():
    from huaqi_src.config.paths import get_learning_dir
    from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore

    try:
        return LearningProgressStore(get_learning_dir())
    except RuntimeError:
        return None


def _run_learning_push():
    from huaqi_src.layers.capabilities.learning.course_generator import CourseGenerator
    try:
        store = _get_learning_store()
        if store is None:
            return
        courses = store.list_courses()
        active = [c for c in courses if c.current_lesson <= c.total_lessons and
                  any(l.status != "completed" for l in c.lessons)][:2]
        if not active:
            print("[LearningPush] 暂无进行中的课程")
            return
        gen = CourseGenerator()
        for course in active:
            current = next(
                (l for l in course.lessons if l.index == course.current_lesson), None
            )
            if current is None:
                continue
            quiz = gen.generate_quiz(course.skill_name, current.title)
            print(f"[LearningPush] 📚 {course.skill_name} 每日复习题：")
            print(quiz)
    except Exception as e:
        print(f"[LearningPush] 推送失败: {e}")


KNOWN_JOB_IDS = {
    "morning_brief",
    "daily_report",
    "weekly_report",
    "quarterly_report",
    "learning_daily_push",
}


def _cleanup_unknown_jobs(manager: SchedulerManager):
    try:
        jobs = manager.scheduler.get_jobs()
        for job in jobs:
            if job.id not in KNOWN_JOB_IDS:
                manager.scheduler.remove_job(job.id)
    except Exception:
        pass


def register_default_jobs(manager: SchedulerManager):
    _cleanup_unknown_jobs(manager)
    manager.add_cron_job(
        "morning_brief",
        func=_run_morning_brief,
        cron="0 8 * * *",
    )
    manager.add_cron_job(
        "daily_report",
        func=_run_daily_report,
        cron="0 23 * * *",
    )
    manager.add_cron_job(
        "weekly_report",
        func=_run_weekly_report,
        cron="0 21 * * 0",
    )
    manager.add_cron_job(
        "quarterly_report",
        func=_run_quarterly_report,
        cron="0 22 28-31 3,6,9,12 *",
    )
    manager.add_cron_job(
        "learning_daily_push",
        func=_run_learning_push,
        cron="0 21 * * *",
    )



def process_pending_signals_job(
    signal_store: RawSignalStore,
    pipeline: Any,
    user_id: str,
    batch_size: int = 50,
) -> None:
    pending = signal_store.query(
        RawSignalFilter(user_id=user_id, processed=0, limit=batch_size)
    )
    for signal in pending:
        try:
            pipeline.process(signal)
        except Exception:
            continue


def vectorize_pending_signals_job(
    signal_store: RawSignalStore,
    vector_adapter: Any,
    user_id: str,
    batch_size: int = 50,
) -> None:
    pending = signal_store.query(
        RawSignalFilter(user_id=user_id, vectorized=0, limit=batch_size)
    )
    for signal in pending:
        try:
            from huaqi_src.layers.data.memory.models import VectorDocument
            doc = VectorDocument(
                id=signal.id,
                user_id=signal.user_id,
                content=signal.content,
                metadata={"source_type": signal.source_type.value},
            )
            vector_adapter.upsert(doc)
            signal_store.mark_vectorized(signal.id)
        except Exception:
            continue
