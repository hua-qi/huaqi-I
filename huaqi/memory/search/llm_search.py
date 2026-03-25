"""LLM 相关性搜索

通过 LLM 直接判断查询与记忆的相关性，无需 Embedding
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import re
import json


@dataclass
class RelevanceResult:
    """相关性结果"""
    content: str
    score: float  # 0-1 相关性分数
    reason: str  # LLM 判断理由
    metadata: Dict[str, Any]


class LLMRelevanceSearch:
    """LLM 相关性搜索
    
    使用 LLM 直接判断查询与记忆内容的相关性
    不依赖 Embedding 模型，兼容所有 LLM
    """
    
    RELEVANCE_PROMPT = """请判断以下查询与记忆内容的相关性。

查询: {query}

记忆内容:
{content}

请分析：
1. 这段记忆是否回答了查询？
2. 这段记忆是否包含查询相关的信息？
3. 相关程度如何？（0-1 分）

以 JSON 格式返回：
{{
    "relevant": true/false,
    "score": 0.85,
    "reason": "这段记忆提到了...与查询相关"
}}"""
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
        self.cache: Dict[str, List[RelevanceResult]] = {}
    
    def search(
        self,
        query: str,
        memories: List[Dict[str, Any]],
        top_k: int = 5,
        threshold: float = 0.6
    ) -> List[RelevanceResult]:
        """搜索相关记忆
        
        Args:
            query: 查询文本
            memories: 记忆列表，每项包含 content 和 metadata
            top_k: 返回数量
            threshold: 相关性阈值
            
        Returns:
            List[RelevanceResult]: 按相关性排序的结果
        """
        results = []
        
        # 分批处理，避免一次处理太多
        batch_size = 10
        for i in range(0, len(memories), batch_size):
            batch = memories[i:i + batch_size]
            batch_results = self._evaluate_batch(query, batch)
            results.extend(batch_results)
        
        # 过滤和排序
        results = [r for r in results if r.score >= threshold]
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:top_k]
    
    def _evaluate_batch(
        self,
        query: str,
        memories: List[Dict[str, Any]]
    ) -> List[RelevanceResult]:
        """评估一批记忆的相关性"""
        results = []
        
        # 构建批量提示词
        contents = []
        for i, mem in enumerate(memories):
            content = mem.get("content", "")
            # 截断长文本
            if len(content) > 500:
                content = content[:500] + "..."
            contents.append(f"[{i}] {content}")
        
        contents_str = "\n\n".join(contents)
        batch_prompt = f"""请判断查询与以下 {len(memories)} 段记忆的相关性。

查询: {query}

记忆内容:
{contents_str}

请为每段记忆分析相关性，以 JSON 数组返回：
[
    {{
        "index": 0,
        "relevant": true/false,
        "score": 0.85,
        "reason": "这段记忆提到了..."
    }},
    ...
]"""
        
        try:
            response = self.llm_manager.quick_chat(
                batch_prompt,
                system="你是一个专业的信息检索助手，准确判断文本相关性。只返回 JSON 格式。"
            )
            
            # 解析 JSON
            evaluations = self._parse_json_response(response)
            
            # 匹配结果
            for eval_data in evaluations:
                idx = eval_data.get("index", 0)
                if 0 <= idx < len(memories):
                    mem = memories[idx]
                    results.append(RelevanceResult(
                        content=mem.get("content", ""),
                        score=eval_data.get("score", 0),
                        reason=eval_data.get("reason", ""),
                        metadata=mem.get("metadata", {})
                    ))
        
        except Exception as e:
            # 失败时回退到简单关键词匹配
            results = self._fallback_keyword_match(query, memories)
        
        return results
    
    def _parse_json_response(self, response: str) -> List[Dict]:
        """解析 LLM 返回的 JSON"""
        try:
            # 尝试直接解析
            return json.loads(response)
        except:
            # 尝试提取 JSON 部分
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
        return []
    
    def _fallback_keyword_match(
        self,
        query: str,
        memories: List[Dict[str, Any]]
    ) -> List[RelevanceResult]:
        """回退到关键词匹配"""
        query_words = set(query.lower().split())
        results = []
        
        for mem in memories:
            content = mem.get("content", "").lower()
            content_words = set(content.split())
            
            # 计算重叠词比例
            overlap = query_words & content_words
            if query_words:
                score = len(overlap) / len(query_words)
            else:
                score = 0
            
            results.append(RelevanceResult(
                content=mem.get("content", ""),
                score=min(score * 1.5, 1.0),  # 稍微放大分数
                reason=f"关键词匹配: {', '.join(overlap)}" if overlap else "无关键词匹配",
                metadata=mem.get("metadata", {})
            ))
        
        return results


class SimpleLLMIndex:
    """简单的 LLM 索引（无需向量）"""
    
    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
        self.documents: List[Dict[str, Any]] = []
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """添加文档"""
        self.documents.append({
            "content": content,
            "metadata": metadata or {},
            "added_at": datetime.now().isoformat()
        })
    
    def search(self, query: str, top_k: int = 5) -> List[RelevanceResult]:
        """搜索文档"""
        if not self.documents:
            return []
        
        searcher = LLMRelevanceSearch(self.llm_manager)
        return searcher.search(query, self.documents, top_k=top_k)
    
    def clear(self):
        """清空索引"""
        self.documents.clear()
