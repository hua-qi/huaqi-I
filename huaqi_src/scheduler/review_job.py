from datetime import datetime, timezone, timedelta
from typing import Any, Dict


def _get_engine_and_manager():
    from huaqi_src.config.paths import get_telos_dir
    from huaqi_src.layers.growth.telos.engine import TelosEngine
    from huaqi_src.layers.growth.telos.manager import TelosManager
    from huaqi_src.cli.context import build_llm_manager

    telos_dir = get_telos_dir()
    telos_mgr = TelosManager(telos_dir=telos_dir, git_commit=True)

    llm_mgr = build_llm_manager(temperature=0.3, max_tokens=1000)
    if llm_mgr is None:
        raise RuntimeError("未配置 LLM")

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
        max_tokens=1000,
    )
    engine = TelosEngine(telos_manager=telos_mgr, llm=llm)
    return engine, telos_mgr


def _get_dimension_last_updated(telos_dir, name: str) -> datetime:
    import re
    from pathlib import Path
    p = Path(telos_dir) / f"{name}.md"
    if not p.exists():
        return datetime.now(timezone.utc) - timedelta(days=999)
    text = p.read_text(encoding="utf-8")
    m = re.search(r"updated_at: (\d{4}-\d{2}-\d{2})", text)
    if m:
        return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - timedelta(days=999)


def run_review_job(
    stale_threshold_days: int = 30,
) -> Dict[str, Any]:
    engine, telos_mgr = _get_engine_and_manager()
    now = datetime.now(timezone.utc)

    reviewed = 0
    stale_found = 0

    for dim in telos_mgr.list_active():
        last_updated = _get_dimension_last_updated(telos_mgr._dir, dim.name)
        days_since = (now - last_updated).days
        if days_since >= stale_threshold_days:
            try:
                result = engine.review_stale_dimension(dim.name, days_since_last_signal=days_since)
                reviewed += 1
                if result.is_stale:
                    stale_found += 1
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"复审失败 dim={dim.name}: {e}")

    return {"reviewed": reviewed, "stale_found": stale_found}
