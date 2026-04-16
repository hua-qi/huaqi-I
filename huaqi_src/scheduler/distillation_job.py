from typing import Any, Dict
import asyncio

from huaqi_src.layers.data.raw_signal.models import RawSignalFilter


def _get_signal_store():
    from huaqi_src.config.paths import require_data_dir
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    adapter = SQLiteStorageAdapter(db_path=require_data_dir() / "signals.db")
    return RawSignalStore(adapter=adapter)


def _get_pipeline():
    from huaqi_src.config.paths import get_telos_dir, require_data_dir
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
    from huaqi_src.layers.growth.telos.engine import TelosEngine
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.growth_events import GrowthEventStore

    adapter = SQLiteStorageAdapter(db_path=require_data_dir() / "signals.db")
    signal_store = RawSignalStore(adapter=adapter)
    event_store = GrowthEventStore(adapter=adapter)

    telos_dir = get_telos_dir()
    telos_mgr = TelosManager(telos_dir=telos_dir, git_commit=True)

    from huaqi_src.cli.context import build_llm_manager
    llm_mgr = build_llm_manager(temperature=0.3, max_tokens=2000)
    if llm_mgr is None:
        raise RuntimeError("未配置 LLM，无法运行提炼任务")

    active_name = llm_mgr.get_active_provider()
    if not active_name:
        raise RuntimeError("未配置 LLM")
    cfg = llm_mgr._active_provider.config
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.api_base or None,
        temperature=0.3,
        max_tokens=2000,
    )

    engine = TelosEngine(telos_manager=telos_mgr, llm=llm)
    return DistillationPipeline(
        signal_store=signal_store,
        event_store=event_store,
        telos_manager=telos_mgr,
        engine=engine,
    )


def run_distillation_job(
    user_id: str = "default",
    limit: int = 10,
) -> Dict[str, Any]:
    signal_store = _get_signal_store()
    unprocessed = signal_store.query(
        RawSignalFilter(user_id=user_id, processed=0, limit=limit)
    )

    if not unprocessed:
        return {"processed": 0, "errors": 0}

    pipeline = _get_pipeline()
    processed = 0
    errors = 0

    for signal in unprocessed:
        try:
            asyncio.run(pipeline.process(signal))
            processed += 1
        except Exception as e:
            errors += 1
            import logging
            logging.getLogger(__name__).error(f"提炼失败 signal={signal.id}: {e}")

    return {"processed": processed, "errors": errors}
