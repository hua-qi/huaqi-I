from abc import ABC, abstractmethod
from typing import List
from huaqi_src.layers.data.memory.models import VectorDocument, VectorQuery, VectorResult


class VectorAdapter(ABC):
    @abstractmethod
    def add(self, documents: List[VectorDocument]) -> None:
        ...

    @abstractmethod
    def search(self, query: VectorQuery) -> List[VectorResult]:
        ...

    @abstractmethod
    def delete(self, doc_id: str, user_id: str) -> None:
        ...
