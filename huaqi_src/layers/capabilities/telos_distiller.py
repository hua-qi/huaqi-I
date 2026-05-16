"""TELOS 信号蒸馏入口。

从 RawSignalStore 捞取未处理信号，送入 DistillationPipeline 进行 TELOS 维度提炼。
供 CLI 命令和 GitHub Actions 工作流调用。
"""
import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _get_signal_store():
    from huaqi_src.config.paths import require_data_dir
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    data_dir = require_data_dir()
    return RawSignalStore(adapter=SQLiteStorageAdapter(db_path=data_dir / "raw_signals.db"))


def _get_pipeline():
    from huaqi_src.config.paths import get_telos_dir, require_data_dir
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
    from huaqi_src.layers.growth.telos.engine import TelosEngine
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.layers.growth.telos.growth_events import GrowthEventStore

    data_dir = require_data_dir()
    adapter = SQLiteStorageAdapter(db_path=data_dir / "raw_signals.db")
    signal_store = RawSignalStore(adapter=adapter)
    event_store = GrowthEventStore(adapter=adapter)

    telos_dir = get_telos_dir()
    telos_mgr = TelosManager(telos_dir=telos_dir, git_commit=True)

    from huaqi_src.cli.context import build_llm_manager
    llm_mgr = build_llm_manager(temperature=0.3, max_tokens=2000)
    if llm_mgr is None:
        raise RuntimeError("未配置 LLM，无法运行蒸馏任务")

    active_name = llm_mgr.get_active_provider()
    cfg = llm_mgr._configs[active_name]
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


async def _run_async(limit: int, user_id: str) -> Dict[str, Any]:
    from huaqi_src.layers.data.raw_signal.models import RawSignalFilter

    store = _get_signal_store()
    unprocessed = store.query(
        RawSignalFilter(user_id=user_id, processed=0, limit=limit)
    )
    if not unprocessed:
        return {"processed": 0, "errors": 0}

    pipeline = _get_pipeline()
    processed = 0
    errors = 0
    for signal in unprocessed:
        try:
            await pipeline.process(signal)
            store.mark_processed(signal.id)
            processed += 1
        except Exception as e:
            errors += 1
            logger.error(f"蒸馏失败 signal={signal.id}: {e}")

    return {"processed": processed, "errors": errors}


def run_distillation(limit: int = 10, user_id: str = "default") -> Dict[str, Any]:
    """运行 TELOS 信号蒸馏。

    Args:
        limit: 每次最多处理的信号数。
        user_id: 用户 ID。

    Returns:
        {"processed": N, "errors": M}
    """
    return asyncio.run(_run_async(limit=limit, user_id=user_id))
