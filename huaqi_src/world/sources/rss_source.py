import datetime
import hashlib

import feedparser

from huaqi_src.collectors.document import HuaqiDocument
from huaqi_src.world.base_source import BaseWorldSource


class RSSSource(BaseWorldSource):
    def __init__(self, url: str, name: str = ""):
        self.url = url
        self.name = name or url
        self.source_id = f"rss:{url}"

    def fetch(self) -> list[HuaqiDocument]:
        feed = feedparser.parse(self.url)
        docs = []
        for entry in feed.entries[:20]:
            content = entry.get("summary", entry.get("title", ""))
            title = entry.get("title", "")
            full_content = f"# {title}\n\n{content}"
            doc_id = hashlib.md5(entry.get("link", title).encode()).hexdigest()[:12]
            published = entry.get("published_parsed")
            if published:
                ts = datetime.datetime(*published[:6])
            else:
                ts = datetime.datetime.now()
            docs.append(
                HuaqiDocument(
                    doc_id=doc_id,
                    doc_type="world_news",
                    source=f"rss:{self.url}",
                    content=full_content,
                    timestamp=ts,
                    metadata={"url": entry.get("link", ""), "feed_name": self.name},
                )
            )
        return docs
