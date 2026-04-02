import datetime
from pathlib import Path
from huaqi_src.layers.data.world.storage import WorldNewsStorage
from huaqi_src.layers.data.collectors.document import HuaqiDocument


def test_save_and_load_world_docs(tmp_path):
    storage = WorldNewsStorage(data_dir=tmp_path)
    docs = [
        HuaqiDocument(
            doc_id="w-001",
            doc_type="world_news",
            source="rss:test",
            content="AI 技术突破：大模型性能提升 50%",
            timestamp=datetime.datetime(2026, 3, 30, 7, 0, 0),
        )
    ]
    storage.save(docs, date=datetime.date(2026, 3, 30))

    saved_file = tmp_path / "world" / "2026-03-30.md"
    assert saved_file.exists()
    content = saved_file.read_text(encoding="utf-8")
    assert "AI 技术突破" in content


def test_search_returns_matching_docs(tmp_path):
    storage = WorldNewsStorage(data_dir=tmp_path)
    docs = [
        HuaqiDocument(
            doc_id="w-001",
            doc_type="world_news",
            source="rss:test",
            content="Python 3.14 发布",
            timestamp=datetime.datetime(2026, 3, 30, 7, 0, 0),
        ),
        HuaqiDocument(
            doc_id="w-002",
            doc_type="world_news",
            source="rss:test",
            content="Rust 语言最新动态",
            timestamp=datetime.datetime(2026, 3, 30, 7, 0, 0),
        ),
    ]
    storage.save(docs, date=datetime.date(2026, 3, 30))
    results = storage.search("Python")
    assert len(results) >= 1
    assert any("Python" in r for r in results)


def test_search_returns_empty_when_no_match(tmp_path):
    storage = WorldNewsStorage(data_dir=tmp_path)
    results = storage.search("不可能匹配的词语xyz")
    assert results == []
