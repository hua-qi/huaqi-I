import pytest
from huaqi_src.config.adapters.vector_base import VectorAdapter
from huaqi_src.layers.data.memory.models import VectorDocument, VectorQuery, VectorResult


def test_vector_adapter_is_abstract():
    with pytest.raises(TypeError):
        VectorAdapter()


def test_vector_document_model():
    doc = VectorDocument(id="doc1", user_id="u1", content="test content")
    assert doc.id == "doc1"
    assert doc.metadata == {}


def test_vector_query_model():
    q = VectorQuery(user_id="u1", text="搜索词", top_k=3)
    assert q.top_k == 3
