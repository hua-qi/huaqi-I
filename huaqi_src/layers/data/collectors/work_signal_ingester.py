from datetime import datetime, timezone
from typing import Optional

from huaqi_src.config.errors import DimensionNotFoundError
from huaqi_src.layers.data.collectors.work_data_source import get_work_sources
from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import DimensionLayer


class WorkSignalIngester:

    def __init__(
        self,
        signal_store: RawSignalStore,
        pipeline: DistillationPipeline,
        telos_manager: TelosManager,
        user_id: str,
        claude_md_writer=None,
    ) -> None:
        self._store = signal_store
        self._pipeline = pipeline
        self._mgr = telos_manager
        self._user_id = user_id
        if claude_md_writer is not None:
            self._mgr.on_work_style_updated = claude_md_writer.sync

    async def ingest(self, since: Optional[datetime] = None) -> int:
        self._ensure_work_style_dimension()
        count = 0
        for source in get_work_sources():
            docs = source.fetch_documents(since=since)
            for doc in docs:
                signal = RawSignal(
                    user_id=self._user_id,
                    source_type=SourceType.WORK_DOC,
                    timestamp=datetime.now(timezone.utc),
                    content=doc,
                    metadata={"work_source": source.name},
                )
                self._store.save(signal)
                await self._pipeline.process(signal)
                count += 1
        return count

    def _ensure_work_style_dimension(self) -> None:
        try:
            self._mgr.get("work_style")
        except DimensionNotFoundError:
            self._mgr.create_custom(
                name="work_style",
                layer=DimensionLayer.MIDDLE,
                initial_content="（待积累）",
            )
