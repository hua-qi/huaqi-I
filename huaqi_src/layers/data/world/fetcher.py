from typing import Optional
from huaqi_src.layers.data.collectors.document import HuaqiDocument
from huaqi_src.layers.data.world.base_source import BaseWorldSource


class WorldNewsFetcher:
    def __init__(self, sources: Optional[list] = None):
        self.sources = sources or []

    def fetch_all(self) -> list[HuaqiDocument]:
        docs = []
        for source in self.sources:
            try:
                results = source.fetch()
                docs.extend(results)
            except Exception as e:
                print(f"[WorldNewsFetcher] 数据源 {source.source_id} 失败: {e}")
        return docs
