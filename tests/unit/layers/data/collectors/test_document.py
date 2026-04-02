from huaqi_src.layers.data.collectors.document import HuaqiDocument
import datetime

def test_document_creation():
    doc = HuaqiDocument(
        doc_id="test-001",
        doc_type="work_doc",
        source="file:/tmp/note.md",
        content="今天完成了项目 A 的设计文档",
        timestamp=datetime.datetime(2026, 3, 30, 10, 0, 0),
    )
    assert doc.doc_id == "test-001"
    assert doc.doc_type == "work_doc"
    assert doc.people == []
    assert doc.summary == ""
    assert doc.metadata == {}

def test_document_to_dict():
    doc = HuaqiDocument(
        doc_id="test-002",
        doc_type="world_news",
        source="rss:https://example.com/feed",
        content="AI 技术最新进展",
        timestamp=datetime.datetime(2026, 3, 30, 7, 0, 0),
        people=["张三"],
        metadata={"url": "https://example.com/1"},
    )
    d = doc.to_dict()
    assert d["doc_id"] == "test-002"
    assert d["people"] == ["张三"]
    assert "timestamp" in d
