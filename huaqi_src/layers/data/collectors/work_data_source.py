from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional


class WorkDataSource(ABC):
    name: str
    source_type: str

    @abstractmethod
    def fetch_documents(self, since: Optional[datetime] = None) -> List[str]:
        pass


_work_source_registry: list = []


def register_work_source(source: WorkDataSource) -> None:
    _work_source_registry.append(source)


def get_work_sources() -> list:
    return list(_work_source_registry)
