"""混合搜索

结合多种搜索策略：BM25 + LLM 相关性判断
无需 Embedding，纯算法 + LLM
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .text_search import TextSearch, TextSearchResult
from .llm_search import LLMRelevanceSearch, RelevanceResult


@dataclass
class HybridSearchResult:
    """混合搜索结果"""
    content: str
    score: float
    text_score: float
    llm_score: float
    metadata: Dict[str, Any]
    source: str  # "text" / "llm" / "both"


class HybridSearch:
    """混合搜索
    
    策略：
    1. 先用 BM25 快速召回候选集（Top 20）
    2. 再用 LLM 精确判断相关性（Top 5）
    3. 融合两种分数得到最终排序
    
    优势：
    - 比纯 LLM 快（减少 LLM 调用次数）
    - 比纯文本准（LLM 语义理解）
    - 无需 Embedding（兼容所有 LLM）
    """
    
    def __init__(self, llm_manager, text_algorithm: str = "bm25"):
        self.llm_manager = llm_manager
        self.text_search = TextSearch(algorithm=text_algorithm)
        self.llm_search = LLMRelevanceSearch(llm_manager)
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """添加文档"""
        self.text_search.add_document(content, metadata)
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """批量添加文档"""
        self.text_search.add_documents(documents)
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        recall_k: int = 20,
        use_llm: bool = True
    ) -> List[HybridSearchResult]:
        """混合搜索
        
        Args:
            query: 查询文本
            top_k: 最终结果数量
            recall_k: 召回阶段数量（给 LLM 的候选集大小）
            use_llm: 是否使用 LLM 精排（false 则只用文本搜索）
            
        Returns:
            List[HybridSearchResult]: 排序后的结果
        """
        # 第一阶段：文本搜索召回
        text_results = self.text_search.search(query, top_k=recall_k)
        
        if not text_results:
            return []
        
        if not use_llm:
            # 不使用 LLM，直接返回文本搜索结果
            return [
                HybridSearchResult(
                    content=r.content,
                    score=r.score,
                    text_score=r.score,
                    llm_score=0,
                    metadata=r.metadata,
                    source="text"
                )
                for r in text_results[:top_k]
            ]
        
        # 第二阶段：LLM 精排
        candidates = [
            {"content": r.content, "metadata": r.metadata}
            for r in text_results
        ]
        
        llm_results = self.llm_search.search(
            query, candidates, top_k=top_k, threshold=0.3
        )
        
        # 第三阶段：融合排序
        # 构建内容 -> 分数的映射
        text_score_map = {r.content: r.score for r in text_results}
        llm_score_map = {r.content: r.score for r in llm_results}
        
        # 合并所有候选
        all_contents = set(text_score_map.keys()) | set(llm_score_map.keys())
        
        hybrid_results = []
        for content in all_contents:
            text_score = text_score_map.get(content, 0)
            llm_score = llm_score_map.get(content, 0)
            
            # 确定来源
            if content in text_score_map and content in llm_score_map:
                source = "both"
            elif content in llm_score_map:
                source = "llm"
            else:
                source = "text"
            
            # 融合分数（加权平均）
            # BM25 分数通常较小，适当放大
            normalized_text_score = min(text_score * 2, 1.0)
            
            if source == "both":
                # 都有分数，加权融合
                final_score = 0.4 * normalized_text_score + 0.6 * llm_score
            elif source == "llm":
                # 只有 LLM 分数
                final_score = llm_score * 0.9  # 稍微降权
            else:
                # 只有文本分数
                final_score = normalized_text_score * 0.8
            
            # 获取元数据
            metadata = {}
            for r in text_results:
                if r.content == content:
                    metadata = r.metadata
                    break
            for r in llm_results:
                if r.content == content:
                    metadata.update(r.metadata)
                    break
            
            hybrid_results.append(HybridSearchResult(
                content=content,
                score=final_score,
                text_score=text_score,
                llm_score=llm_score,
                metadata=metadata,
                source=source
            ))
        
        # 按最终分数排序
        hybrid_results.sort(key=lambda x: x.score, reverse=True)
        
        return hybrid_results[:top_k]
    
    def search_with_explanation(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """带解释的搜索（适合调试）"""
        results = self.search(query, top_k=top_k)
        
        return [
            {
                "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                "final_score": round(r.score, 3),
                "text_score": round(r.text_score, 3),
                "llm_score": round(r.llm_score, 3),
                "source": r.source,
                "metadata": r.metadata
            }
            for r in results
        ]
    
    def clear(self):
        """清空索引"""
        self.text_search.clear()


class LazyHybridSearch(HybridSearch):
    """延迟构建索引的混合搜索
    
    适合文档动态增长的场景
    """
    
    def __init__(self, llm_manager, auto_build_threshold: int = 10):
        super().__init__(llm_manager)
        self.pending_docs: List[Dict[str, Any]] = []
        self.auto_build_threshold = auto_build_threshold
        self._dirty = False
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """添加文档（延迟索引）"""
        self.pending_docs.append({
            "content": content,
            "metadata": metadata or {}
        })
        self._dirty = True
        
        # 达到阈值自动构建
        if len(self.pending_docs) >= self.auto_build_threshold:
            self._build_pending()
    
    def _build_pending(self):
        """构建待处理文档的索引"""
        if not self.pending_docs:
            return
        
        for doc in self.pending_docs:
            super().add_document(doc["content"], doc["metadata"])
        
        self.pending_docs.clear()
        self._dirty = False
    
    def search(self, query: str, top_k: int = 5, **kwargs) -> List[HybridSearchResult]:
        """搜索（自动构建索引）"""
        if self._dirty:
            self._build_pending()
        
        return super().search(query, top_k=top_k, **kwargs)
