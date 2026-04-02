from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.layers.growth.telos.engine import TelosEngine, SignalStrength
from huaqi_src.layers.growth.telos.growth_events import GrowthEvent, GrowthEventStore
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSION_LAYERS


class DistillationPipeline:
    """信号提炼管道：将 RawSignal 通过 5 步提炼写入 TELOS。

    负责编排 Step1~Step5 的调用顺序，以及读写 RawSignalStore / GrowthEventStore。
    """

    def __init__(
        self,
        signal_store: RawSignalStore,
        event_store: GrowthEventStore,
        telos_manager: TelosManager,
        engine: TelosEngine,
        signal_threshold: int = 3,
        days_window: int = 30,
    ) -> None:
        self._signal_store = signal_store
        self._event_store = event_store
        self._mgr = telos_manager
        self._engine = engine
        self._threshold = signal_threshold
        self._days_window = days_window

    def process(self, signal: RawSignal) -> Dict[str, Any]:
        """处理单条信号，返回处理结果摘要。"""
        step1_result = self._engine.step1_analyze(signal)
        self._signal_store.mark_processed(signal.id)

        results: Dict[str, Any] = {
            "signal_id": signal.id,
            "step1": step1_result,
            "pipeline_runs": [],
        }

        for dimension in step1_result.dimensions:
            since = datetime.now(timezone.utc) - timedelta(days=self._days_window)
            is_strong = step1_result.signal_strength == SignalStrength.STRONG

            count = self._signal_store.count(
                RawSignalFilter(user_id=signal.user_id, processed=1, since=since)
            )
            if not is_strong and count < self._threshold:
                continue

            unprocessed = self._signal_store.query(
                RawSignalFilter(user_id=signal.user_id, processed=1, since=since, limit=self._threshold * 3)
            )
            summaries = [s.content[:80] for s in unprocessed if dimension in (s.metadata or {})]
            if not summaries:
                summaries = [s.content[:80] for s in unprocessed[: self._threshold]]

            run_result = self._engine.run_pipeline(
                signal=signal,
                step1_result=step1_result,
                signal_summaries=summaries,
                days=self._days_window,
            )

            if run_result["updated"] and run_result["growth_event"]:
                step5 = run_result["growth_event"]
                if step5.is_growth_event:
                    dim = self._mgr.get(dimension)
                    layer = STANDARD_DIMENSION_LAYERS.get(dimension)
                    event = GrowthEvent(
                        user_id=signal.user_id,
                        dimension=dimension,
                        layer=layer.value if layer else "surface",
                        title=step5.title,
                        narrative=step5.narrative,
                        new_content=dim.content,
                        trigger_signals=[signal.id],
                        occurred_at=signal.timestamp,
                    )
                    self._event_store.save(event)
                    run_result["saved_event"] = event

            results["pipeline_runs"].append(run_result)

        return results
