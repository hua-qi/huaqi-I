from abc import ABC, abstractmethod
from huaqi_src.collectors.document import HuaqiDocument


class BaseWorldSource(ABC):
    source_id: str = ""

    @abstractmethod
    def fetch(self) -> list[HuaqiDocument]:
        """抓取最新数据，返回 HuaqiDocument 列表"""
        ...
