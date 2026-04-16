from typing import Any, Optional

from huaqi_src.scheduler.manager import SchedulerManager
from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore
from huaqi_src.scheduler.job_runner import _run_scheduled_job
from huaqi_src.layers.data.raw_signal.models import RawSignalFilter
from huaqi_src.layers.data.raw_signal.store import RawSignalStore


def register_jobs(manager: SchedulerManager, store: ScheduledJobStore):
    jobs = store.load_jobs()
    enabled_ids = {job.id for job in jobs if job.enabled}

    try:
        existing = manager.list_jobs()
        for apj in existing:
            if apj["id"] not in enabled_ids:
                manager.remove_job(apj["id"])
    except Exception as e:
        print(f"[Scheduler] 清理过期任务失败: {e}")

    for job in jobs:
        if not job.enabled:
            continue
        manager.add_cron_job(
            job.id,
            func=_run_scheduled_job,
            cron=job.cron,
            kwargs={"job_id": job.id, "prompt": job.prompt, "output_dir": job.output_dir},
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


def register_distillation_job(
    scheduler_adapter,
    interval_seconds: int = 3600,
    user_id: str = "default",
    limit: int = 10,
) -> None:
    from huaqi_src.scheduler.distillation_job import run_distillation_job

    def _job():
        run_distillation_job(user_id=user_id, limit=limit)

    scheduler_adapter.add_interval_job(
        func=_job,
        seconds=interval_seconds,
        job_id="distillation_job",
    )


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
