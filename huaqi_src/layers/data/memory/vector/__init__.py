"""向量存储模块 - Chroma + Embedding + 混合检索"""

from __future__ import annotations


def get_chroma_client(*args, **kwargs):
    from .chroma_client import get_chroma_client as _get
    return _get(*args, **kwargs)


def get_embedding_service(*args, **kwargs):
    from .embedder import get_embedding_service as _get
    return _get(*args, **kwargs)


def get_hybrid_search(*args, **kwargs):
    from .hybrid_search import get_hybrid_search as _get
    return _get(*args, **kwargs)


def __getattr__(name: str):
    if name == "ChromaClient":
        from .chroma_client import ChromaClient
        return ChromaClient
    if name == "EmbeddingService":
        from .embedder import EmbeddingService
        return EmbeddingService
    if name == "HybridSearch":
        from .hybrid_search import HybridSearch
        return HybridSearch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ChromaClient",
    "get_chroma_client",
    "EmbeddingService",
    "get_embedding_service",
    "HybridSearch",
    "get_hybrid_search",
]
