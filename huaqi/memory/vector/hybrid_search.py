"""BM25 + 向量 混合检索

融合文本匹配和语义相似度，提供更准确的搜索结果。
"""

import math
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from .chroma_client import ChromaClient, get_chroma_client
from .embedder import EmbeddingService, get_embedding_service


class HybridSearch:
    """混合检索引擎
    
    融合策略:
    - BM25: 精确匹配关键词
    - 向量相似度: 语义匹配
    - 时间衰减: 近期内容加权
    
    公式: final_score = alpha * vector_score + (1-alpha) * bm25_score + recency_boost
    """
    
    def __init__(
        self,
        chroma_client: Optional[ChromaClient] = None,
        embedder: Optional[EmbeddingService] = None,
        alpha: float = 0.7,  # 向量权重
        beta: float = 0.1,   # 时间衰减系数
        use_bm25: bool = True,
        use_vector: bool = True,
    ):
        """初始化混合检索
        
        Args:
            chroma_client: Chroma 客户端
            embedder: Embedding 服务
            alpha: 向量搜索权重 (0-1)
            beta: 时间衰减系数
            use_bm25: 是否使用 BM25
            use_vector: 是否使用向量搜索
        """
        self.chroma = chroma_client or get_chroma_client()
        self.embedder = embedder
        self.alpha = alpha
        self.beta = beta
        self.use_bm25 = use_bm25
        self.use_vector = use_vector
        
        # BM25 索引缓存
        self._bm25: Optional[BM25Okapi] = None
        self._bm25_docs: List[Dict[str, Any]] = []
        self._bm25_last_update: Optional[datetime] = None
    
    def _tokenize(self, text: str) -> List[str]:
        """中文分词 (简单版)
        
        实际项目中可以使用 jieba 等分词工具
        """
        # 移除特殊字符
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # 按空格分割
        tokens = text.split()
        return tokens
    
    def _build_bm25_index(self, force_refresh: bool = False):
        """构建 BM25 索引"""
        # 检查是否需要刷新 (每5分钟刷新一次)
        if not force_refresh and self._bm25 is not None:
            if self._bm25_last_update:
                elapsed = datetime.now() - self._bm25_last_update
                if elapsed < timedelta(minutes=5):
                    return
        
        # 导出所有文档
        docs = self.chroma.export_all()
        if not docs:
            self._bm25 = None
            self._bm25_docs = []
            return
        
        # 分词
        tokenized_docs = [self._tokenize(doc["content"]) for doc in docs]
        
        # 构建 BM25
        self._bm25 = BM25Okapi(tokenized_docs)
        self._bm25_docs = docs
        self._bm25_last_update = datetime.now()
    
    def _calculate_recency_score(self, date_str: str) -> float:
        """计算时间衰减分数
        
        使用指数衰减: score = exp(-beta * days_ago)
        """
        try:
            if isinstance(date_str, str):
                doc_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                return 0.5  # 默认分数
            
            days_ago = (datetime.now() - doc_date).days
            score = math.exp(-self.beta * max(0, days_ago))
            return score
        except:
            return 0.5  # 默认分数
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_type: Optional[str] = None,
        use_bm25: Optional[bool] = None,
        use_vector: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """混合搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            doc_type: 文档类型过滤 (diary, conversation, etc.)
            use_bm25: 是否使用 BM25 (默认使用全局设置)
            use_vector: 是否使用向量搜索 (默认使用全局设置)
            
        Returns:
            搜索结果列表，按综合分数排序
        """
        use_bm25 = use_bm25 if use_bm25 is not None else self.use_bm25
        use_vector = use_vector if use_vector is not None else self.use_vector
        
        results = {}
        
        # 1. 向量搜索
        if use_vector:
            vector_results = self.chroma.search(
                query=query,
                top_k=top_k * 2,  # 多召回一些用于融合
                where={"type": doc_type} if doc_type else None,
            )
            
            for r in vector_results:
                # 距离转相似度 (Chroma 使用余弦距离)
                # 距离越小越相似
                similarity = 1 - r["distance"]
                results[r["id"]] = {
                    "id": r["id"],
                    "content": r["content"],
                    "metadata": r["metadata"],
                    "vector_score": similarity,
                    "bm25_score": 0.0,
                }
        
        # 2. BM25 搜索
        if use_bm25:
            self._build_bm25_index()
            
            if self._bm25 and self._bm25_docs:
                query_tokens = self._tokenize(query)
                bm25_scores = self._bm25.get_scores(query_tokens)
                
                # 获取 top_k*2 个 BM25 结果
                top_indices = np.argsort(bm25_scores)[::-1][:top_k*2]
                
                for idx in top_indices:
                    if bm25_scores[idx] <= 0:
                        continue
                    
                    doc = self._bm25_docs[idx]
                    doc_id = doc["id"]
                    
                    # 类型过滤
                    if doc_type and doc.get("metadata", {}).get("type") != doc_type:
                        continue
                    
                    if doc_id in results:
                        results[doc_id]["bm25_score"] = bm25_scores[idx]
                    else:
                        results[doc_id] = {
                            "id": doc_id,
                            "content": doc["content"],
                            "metadata": doc["metadata"],
                            "vector_score": 0.0,
                            "bm25_score": bm25_scores[idx],
                        }
        
        # 3. 融合分数
        final_results = []
        for doc_id, data in results.items():
            # 归一化 BM25 分数 (简单归一化)
            bm25_normalized = min(1.0, data["bm25_score"] / 10.0)
            
            # 融合分数
            fused_score = (
                self.alpha * data["vector_score"] +
                (1 - self.alpha) * bm25_normalized
            )
            
            # 时间衰减加分
            date_str = data["metadata"].get("date", data["metadata"].get("created_at", ""))
            recency_score = self._calculate_recency_score(date_str)
            
            # 最终分数 (加入时间因子)
            final_score = 0.9 * fused_score + 0.1 * recency_score
            
            final_results.append({
                "id": doc_id,
                "content": data["content"],
                "metadata": data["metadata"],
                "score": final_score,
                "vector_score": data["vector_score"],
                "bm25_score": bm25_normalized,
                "recency_score": recency_score,
            })
        
        # 按分数排序
        final_results.sort(key=lambda x: x["score"], reverse=True)
        
        return final_results[:top_k]
    
    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """添加文档到索引
        
        Args:
            doc_id: 文档ID
            content: 内容
            metadata: 元数据
        """
        # 添加到 Chroma
        success = self.chroma.add(doc_id, content, metadata)
        
        # 标记 BM25 需要刷新
        if success and self._bm25 is not None:
            self._bm25_last_update = None
        
        return success
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        success = self.chroma.delete(doc_id)
        
        # 标记 BM25 需要刷新
        if success and self._bm25 is not None:
            self._bm25_last_update = None
        
        return success
    
    def refresh_index(self):
        """刷新索引"""
        self._build_bm25_index(force_refresh=True)


# 单例
_hybrid_search: Optional[HybridSearch] = None


def get_hybrid_search(
    alpha: float = 0.7,
    use_bm25: bool = True,
    use_vector: bool = True,
) -> HybridSearch:
    """获取混合检索单例"""
    global _hybrid_search
    if _hybrid_search is None:
        _hybrid_search = HybridSearch(
            alpha=alpha,
            use_bm25=use_bm25,
            use_vector=use_vector,
        )
    return _hybrid_search
