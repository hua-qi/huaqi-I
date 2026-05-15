import datetime
from unittest.mock import MagicMock, patch

from huaqi_src.layers.data.world.sources.rss_source import RSSSource


def _make_entry(title, link, summary, published_parsed):
    """创建一个模拟的 feedparser entry。"""
    entry = MagicMock()
    entry.get = lambda key, default=None: {
        "title": title,
        "link": link,
        "summary": summary,
    }.get(key, default)
    entry.configure_mock(
        title=title,
        link=link,
        summary=summary,
        published_parsed=published_parsed,
    )
    return entry


class TestRSSSource:
    def test_content_contains_link(self):
        """AC-1: RSS 条目 content 包含原文链接行。"""
        mock_entry = _make_entry(
            title="Test News",
            link="https://example.com/news/1",
            summary="Summary text",
            published_parsed=datetime.datetime(2026, 5, 15, 8, 0).timetuple(),
        )
        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        with patch("feedparser.parse", return_value=mock_feed):
            source = RSSSource(url="https://example.com/feed", name="TestSource")
            docs = source.fetch()
            assert len(docs) == 1
            assert "**链接**" in docs[0].content
            assert "https://example.com/news/1" in docs[0].content

    def test_content_starts_with_title(self):
        """内容仍然以标题开头。"""
        mock_entry = _make_entry(
            title="Breaking News",
            link="https://example.com/news/2",
            summary="Some summary",
            published_parsed=None,
        )
        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        with patch("feedparser.parse", return_value=mock_feed):
            source = RSSSource(url="https://example.com/feed", name="TS")
            docs = source.fetch()
            assert docs[0].content.startswith("# Breaking News")
