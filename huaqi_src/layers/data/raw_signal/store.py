from typing import List, Optional

from huaqi_src.config.adapters.storage_base import StorageAdapter
from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter


class RawSignalStore:

    def __init__(self, adapter: StorageAdapter) -> None:
        self._adapter = adapter

    def save(self, signal: RawSignal) -> None:
        self._adapter.save(signal)

    def get(self, signal_id: str) -> Optional[RawSignal]:
        return self._adapter.get(signal_id)

    def query(self, filter: RawSignalFilter) -> List[RawSignal]:
        return self._adapter.query(filter)

    def mark_processed(self, signal_id: str) -> None:
        self._adapter.mark_processed(signal_id)

    def mark_distilled(self, signal_id: str) -> None:
        self._adapter.mark_distilled(signal_id)

    def mark_vectorized(self, signal_id: str) -> None:
        self._adapter.mark_vectorized(signal_id)

    def count(self, filter: RawSignalFilter) -> int:
        return self._adapter.count(filter)
