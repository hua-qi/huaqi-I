import datetime
from pathlib import Path
from typing import Optional

from huaqi_src.layers.data.world.fetcher import WorldNewsFetcher
from huaqi_src.layers.data.world.storage import WorldNewsStorage
from huaqi_src.layers.data.world.sources.rss_source import RSSSource

DEFAULT_RSS_FEEDS = [
    ("https://feeds.bbci.co.uk/news/technology/rss.xml", "BBC科技"),
    ("https://rss.cnn.com/rss/money_news_international.rss", "CNN财经"),
    ("https://feeds.reuters.com/reuters/worldNews", "路透社国际"),
]


class WorldPipeline:
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            from huaqi_src.config.paths import require_data_dir
            self._data_dir = require_data_dir()

    def run(self, date: Optional[datetime.date] = None) -> bool:
        try:
            sources = [RSSSource(url, name) for url, name in DEFAULT_RSS_FEEDS]
            fetcher = WorldNewsFetcher(sources=sources)
            docs = fetcher.fetch_all()
            if not docs:
                print("[WorldPipeline] 未获取到任何文档")
                return False
            storage = WorldNewsStorage(data_dir=self._data_dir)
            storage.save(docs, date=date)
            print(f"[WorldPipeline] 已保存 {len(docs)} 篇文档")
            return True
        except Exception as e:
            print(f"[WorldPipeline] 执行失败: {e}")
            return False
