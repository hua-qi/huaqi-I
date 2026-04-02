import pytest
from unittest.mock import patch, MagicMock
from huaqi_src.layers.data.world.fetcher import WorldNewsFetcher
from huaqi_src.layers.data.world.base_source import BaseWorldSource
from huaqi_src.layers.data.collectors.document import HuaqiDocument
import datetime


class FakeSource(BaseWorldSource):
    source_id = "fake"

    def fetch(self) -> list[HuaqiDocument]:
        return [
            HuaqiDocument(
                doc_id="fake-001",
                doc_type="world_news",
                source="fake:test",
                content="测试新闻内容",
                timestamp=datetime.datetime.now(),
            )
        ]


def test_fetcher_returns_documents_from_source():
    fetcher = WorldNewsFetcher(sources=[FakeSource()])
    docs = fetcher.fetch_all()
    assert len(docs) == 1
    assert docs[0].doc_type == "world_news"


def test_fetcher_handles_source_exception_gracefully():
    class BrokenSource(BaseWorldSource):
        source_id = "broken"

        def fetch(self) -> list[HuaqiDocument]:
            raise RuntimeError("网络超时")

    fetcher = WorldNewsFetcher(sources=[BrokenSource(), FakeSource()])
    docs = fetcher.fetch_all()
    assert len(docs) == 1


def test_fetcher_with_no_sources_returns_empty():
    fetcher = WorldNewsFetcher(sources=[])
    docs = fetcher.fetch_all()
    assert docs == []
