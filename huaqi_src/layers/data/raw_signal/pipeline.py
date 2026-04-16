import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.layers.growth.telos.engine import TelosEngine, SignalStrength
from huaqi_src.layers.growth.telos.growth_events import GrowthEvent, GrowthEventStore
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSION_LAYERS, DimensionLayer
from huaqi_src.config.errors import DimensionNotFoundError


class DistillationPipeline:

    def __init__(
        self,
        signal_store: RawSignalStore,
        event_store: GrowthEventStore,
        telos_manager: TelosManager,
        engine: TelosEngine,
        signal_threshold: int = 3,
        days_window: int = 30,
        person_extractor=None,
        people_pipeline=None,
    ) -> None:
        self._signal_store = signal_store
        self._event_store = event_store
        self._mgr = telos_manager
        self._engine = engine
        self._threshold = signal_threshold
        self._days_window = days_window
        self._person_extractor = person_extractor
        self._people_pipeline = people_pipeline

    async def process(self, signal: RawSignal) -> Dict[str, Any]:
        step1_result = self._engine.step1_analyze(signal)
        self._signal_store.mark_processed(signal.id)

        if step1_result.new_dimension_hint:
            hint = step1_result.new_dimension_hint
            try:
                self._mgr.get(hint)
            except DimensionNotFoundError:
                self._mgr.create_custom(
                    name=hint,
                    layer=DimensionLayer.SURFACE,
                    initial_content="（待积累）",
                )
            if hint not in step1_result.dimensions:
                step1_result.dimensions.append(hint)

        results: Dict[str, Any] = {
            "signal_id": signal.id,
            "step1": step1_result,
            "pipeline_runs": [],
        }

        since = datetime.now(timezone.utc) - timedelta(days=self._days_window)
        is_strong = step1_result.signal_strength == SignalStrength.STRONG

        count = self._signal_store.count(
            RawSignalFilter(user_id=signal.user_id, processed=1, since=since)
        )

        if not is_strong and count < self._threshold:
            if step1_result.has_people:
                await self._run_people(signal, step1_result.mentioned_names)
            return results

        recent_signals = self._signal_store.query(
            RawSignalFilter(user_id=signal.user_id, processed=1, since=since, limit=self._threshold * 3)
        )

        async def process_dimension(dimension: str) -> Optional[Dict[str, Any]]:
            try:
                summaries = [s.content[:80] for s in recent_signals if dimension in (s.metadata or {})]
                if not summaries:
                    summaries = [s.content[:80] for s in recent_signals[:self._threshold]]

                combined_result = await self._engine.step345_combined(
                    dimension=dimension,
                    signal_summaries=summaries,
                    days=self._days_window,
                    recent_signal_count=count,
                )

                run_result: Dict[str, Any] = {
                    "updated": combined_result.should_update,
                    "growth_event": None,
                }

                if combined_result.should_update and combined_result.is_growth_event:
                    dim = self._mgr.get(dimension)
                    layer = STANDARD_DIMENSION_LAYERS.get(dimension)
                    event = GrowthEvent(
                        user_id=signal.user_id,
                        dimension=dimension,
                        layer=layer.value if layer else "surface",
                        title=combined_result.growth_title or "",
                        narrative=combined_result.growth_narrative or "",
                        new_content=dim.content,
                        trigger_signals=[signal.id],
                        occurred_at=signal.timestamp,
                    )
                    self._event_store.save(event)
                    run_result["growth_event"] = combined_result
                    run_result["saved_event"] = event

                return run_result
            except Exception:
                return None

        tasks = [process_dimension(dim) for dim in step1_result.dimensions]

        if step1_result.has_people:
            tasks.append(self._run_people(signal, step1_result.mentioned_names))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        pipeline_runs = [r for r in all_results[:len(step1_result.dimensions)] if r is not None and not isinstance(r, Exception)]
        results["pipeline_runs"] = pipeline_runs

        return results

    async def _run_people(self, signal: RawSignal, mentioned_names: list) -> None:
        if self._people_pipeline is not None:
            try:
                await self._people_pipeline.process(
                    signal=signal,
                    mentioned_names=mentioned_names,
                )
            except Exception:
                pass
        elif self._person_extractor is not None:
            try:
                self._person_extractor.extract_from_text(signal.content)
            except Exception:
                pass
