"""文本搜索算法

纯算法实现：TF-IDF + BM25
无需 Embedding，兼容所有环境
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Counter
from dataclasses import dataclass
from collections import defaultdict
import math
import re
import json


@dataclass
class TextSearchResult:
    """文本搜索结果"""
    content: str
    score: float
    metadata: Dict[str, Any]
    matched_terms: List[str]


class TFIDFSearch:
    """TF-IDF 文本搜索"""
    
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.doc_freq: Dict[str, int] = defaultdict(int)  # 文档频率
        self.idf: Dict[str, float] = {}  # IDF 值
        self.doc_vectors: List[Dict[str, float]] = []  # 文档向量（稀疏）
        self.N: int = 0  # 文档总数
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        # 简单分词：按非字母数字字符分割，转小写
        words = re.findall(r'\b[a-zA-Z\u4e00-\u9fa5]+\b', text.lower())
        # 过滤停用词（简单版）
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                      '的', '了', '在', '是', '和', '有', '我', '你', '它'}
        return [w for w in words if w not in stop_words and len(w) > 1]
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """添加文档"""
        tokens = self._tokenize(content)
        token_set = set(tokens)
        
        self.documents.append({
            "content": content,
            "metadata": metadata or {},
            "tokens": tokens,
            "token_set": token_set
        })
        
        # 更新文档频率
        for token in token_set:
            self.doc_freq[token] += 1
        
        self.N += 1
    
    def build_index(self):
        """构建索引（计算 IDF 和文档向量）"""
        if self.N == 0:
            return
        
        # 计算 IDF
        for term, freq in self.doc_freq.items():
            self.idf[term] = math.log((self.N + 1) / (freq + 1)) + 1
        
        # 计算文档向量（TF-IDF）
        self.doc_vectors = []
        for doc in self.documents:
            tf = Counter(doc["tokens"])
            vector = {}
            for term, count in tf.items():
                if term in self.idf:
                    vector[term] = (1 + math.log(count)) * self.idf[term]
            
            # L2 归一化
            norm = math.sqrt(sum(v**2 for v in vector.values()))
            if norm > 0:
                vector = {k: v/norm for k, v in vector.items()}
            
            self.doc_vectors.append(vector)
    
    def search(self, query: str, top_k: int = 5) -> List[TextSearchResult]:
        """搜索"""
        if not self.documents:
            return []
        
        # 确保索引已构建
        if not self.idf:
            self.build_index()
        
        # 处理查询
        query_tokens = self._tokenize(query)
        query_tf = Counter(query_tokens)
        
        # 计算查询向量
        query_vector = {}
        for term, count in query_tf.items():
            if term in self.idf:
                query_vector[term] = (1 + math.log(count)) * self.idf[term]
        
        # L2 归一化
        norm = math.sqrt(sum(v**2 for v in query_vector.values()))
        if norm > 0:
            query_vector = {k: v/norm for k, v in query_vector.items()}
        
        # 计算相似度（点积）
        scores = []
        for i, doc_vector in enumerate(self.doc_vectors):
            score = sum(query_vector.get(term, 0) * doc_vector.get(term, 0) 
                       for term in set(query_vector) & set(doc_vector))
            
            # 记录匹配的术语
            matched = [t for t in query_tokens if t in self.documents[i]["token_set"]]
            
            scores.append((i, score, matched))
        
        # 排序并返回
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for idx, score, matched in scores[:top_k]:
            if score > 0:
                doc = self.documents[idx]
                results.append(TextSearchResult(
                    content=doc["content"],
                    score=score,
                    metadata=doc["metadata"],
                    matched_terms=matched
                ))
        
        return results
    
    def clear(self):
        """清空索引"""
        self.documents.clear()
        self.doc_freq.clear()
        self.idf.clear()
        self.doc_vectors.clear()
        self.N = 0


class BM25Search:
    """BM25 文本搜索（比 TF-IDF 更适合短文本）"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1  # 词频饱和度参数
        self.b = b    # 文档长度归一化参数
        
        self.documents: List[Dict[str, Any]] = []
        self.doc_freq: Dict[str, int] = defaultdict(int)
        self.idf: Dict[str, float] = {}
        self.avgdl: float = 0  # 平均文档长度
        self.N: int = 0
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        words = re.findall(r'\b[a-zA-Z\u4e00-\u9fa5]+\b', text.lower())
        stop_words = {'the', 'a', 'an', 'is', 'are', '的', '了', '在', '是', '和'}
        return [w for w in words if w not in stop_words and len(w) > 1]
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """添加文档"""
        tokens = self._tokenize(content)
        token_set = set(tokens)
        
        self.documents.append({
            "content": content,
            "metadata": metadata or {},
            "tokens": tokens,
            "length": len(tokens)
        })
        
        for token in token_set:
            self.doc_freq[token] += 1
        
        self.N += 1
        self.avgdl = sum(d["length"] for d in self.documents) / self.N
    
    def build_index(self):
        """构建索引"""
        if self.N == 0:
            return
        
        # 计算 IDF（BM25 版本）
        for term, freq in self.doc_freq.items():
            self.idf[term] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1)
    
    def search(self, query: str, top_k: int = 5) -> List[TextSearchResult]:
        """BM25 搜索"""
        if not self.documents:
            return []
        
        if not self.idf:
            self.build_index()
        
        query_tokens = self._tokenize(query)
        query_tf = Counter(query_tokens)
        
        scores = []
        
        for i, doc in enumerate(self.documents):
            score = 0
            matched = []
            
            doc_tokens = doc["tokens"]
            doc_length = doc["length"]
            doc_tf = Counter(doc_tokens)
            
            for term in query_tf:
                if term not in self.idf:
                    continue
                
                f = doc_tf.get(term, 0)  # 词频
                idf = self.idf[term]
                
                # BM25 公式
                numerator = f * (self.k1 + 1)
                denominator = f + self.k1 * (1 - self.b + self.b * (doc_length / self.avgdl))
                score += idf * numerator / denominator
                
                if f > 0:
                    matched.append(term)
            
            scores.append((i, score, matched))
        
        # 排序
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for idx, score, matched in scores[:top_k]:
            if score > 0:
                doc = self.documents[idx]
                results.append(TextSearchResult(
                    content=doc["content"],
                    score=min(score / 10, 1.0),  # 归一化到 0-1
                    metadata=doc["metadata"],
                    matched_terms=matched
                ))
        
        return results


class TextSearch:
    """文本搜索统一接口"""
    
    def __init__(self, algorithm: str = "bm25"):
        """
        Args:
            algorithm: "tfidf" 或 "bm25"
        """
        if algorithm == "tfidf":
            self.engine = TFIDFSearch()
        else:
            self.engine = BM25Search()
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """添加文档"""
        self.engine.add_document(content, metadata)
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """批量添加文档"""
        for doc in documents:
            self.add_document(
                doc.get("content", ""),
                doc.get("metadata", {})
            )
        self.engine.build_index()
    
    def search(self, query: str, top_k: int = 5) -> List[TextSearchResult]:
        """搜索"""
        return self.engine.search(query, top_k)
    
    def clear(self):
        """清空"""
        self.engine.clear()
