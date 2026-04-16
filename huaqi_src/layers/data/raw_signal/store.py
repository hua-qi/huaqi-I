from typing import List, Optional
import math

from huaqi_src.config.adapters.storage_base import StorageAdapter
from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


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

    def search_by_embedding(
        self,
        user_id: str,
        query_vec: list[float],
        top_k: int = 5,
    ) -> List[RawSignal]:
        all_signals = self.query(RawSignalFilter(user_id=user_id, limit=1000))
        candidates = [s for s in all_signals if s.embedding is not None]
        if not candidates:
            return []
        scored = [(s, _cosine_sim(query_vec, s.embedding)) for s in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:top_k]]
