from abc import ABC, abstractmethod
from typing import List, Optional

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter


class StorageAdapter(ABC):

    @abstractmethod
    def save(self, signal: RawSignal) -> None: ...

    @abstractmethod
    def get(self, signal_id: str) -> Optional[RawSignal]: ...

    @abstractmethod
    def query(self, filter: RawSignalFilter) -> List[RawSignal]: ...

    @abstractmethod
    def mark_processed(self, signal_id: str) -> None: ...

    @abstractmethod
    def mark_distilled(self, signal_id: str) -> None: ...

    @abstractmethod
    def mark_vectorized(self, signal_id: str) -> None: ...

    @abstractmethod
    def count(self, filter: RawSignalFilter) -> int: ...
