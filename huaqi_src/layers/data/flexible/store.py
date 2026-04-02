"""灵活存储层

支持动态字段的存储，基于 JSONL 文件 + Chroma 向量数据库
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

from huaqi_src.config.paths import get_memory_dir


@dataclass
class DimensionValue:
    """维度值"""
    value: Any
    confidence: float = 1.0


@dataclass
class AnalysisResult:
    """分析结果"""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_content: str = ""
    conversation_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    dimensions: Dict[str, DimensionValue] = field(default_factory=dict)
    proposed_dimensions: List[str] = field(default_factory=list)

    def get_dimension(self, dim_id: str) -> Optional[DimensionValue]:
        return self.dimensions.get(dim_id)

    def get_dimension_value(self, dim_id: str) -> Any:
        dim = self.dimensions.get(dim_id)
        return dim.value if dim else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "message_content": self.message_content,
            "conversation_id": self.conversation_id,
            "timestamp": self.timestamp,
            "dimensions": {
                k: {"value": v.value, "confidence": v.confidence}
                for k, v in self.dimensions.items()
            },
            "proposed_dimensions": self.proposed_dimensions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisResult":
        dimensions = {
            k: DimensionValue(value=v["value"], confidence=v.get("confidence", 1.0))
            for k, v in data.get("dimensions", {}).items()
        }
        return cls(
            result_id=data.get("result_id", str(uuid.uuid4())),
            message_content=data.get("message_content", ""),
            conversation_id=data.get("conversation_id", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            dimensions=dimensions,
            proposed_dimensions=data.get("proposed_dimensions", []),
        )


@dataclass
class ContentInteractionEvent:
    """内容交互事件"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str = ""
    source: str = ""  # x/twitter/rss
    title: str = ""
    url: str = ""
    topics: List[str] = field(default_factory=list)
    
    # 用户行为
    actions: List[str] = field(default_factory=list)  # [viewed, summarized, translated, saved, shared, skipped]
    
    # 用户反馈
    user_rating: Optional[int] = None  # 1-5 星
    user_comment: str = ""
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "content_id": self.content_id,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "topics": self.topics,
            "actions": self.actions,
            "user_rating": self.user_rating,
            "user_comment": self.user_comment,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentInteractionEvent":
        return cls(
            event_id=data.get("event_id", ""),
            content_id=data.get("content_id", ""),
            source=data.get("source", ""),
            title=data.get("title", ""),
            url=data.get("url", ""),
            topics=data.get("topics", []),
            actions=data.get("actions", []),
            user_rating=data.get("user_rating"),
            user_comment=data.get("user_comment", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


class FlexibleStore:
    """灵活存储 - 支持动态字段（单用户版本）"""
    
    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or get_memory_dir()
        
        # 分析结果存储
        self.analysis_dir = self.memory_dir / "analysis_results"
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        
        # 内容交互事件存储
        self.content_interactions_dir = self.memory_dir / "content_interactions"
        self.content_interactions_dir.mkdir(parents=True, exist_ok=True)
        
        # Chroma 存储
        self._chroma_client = None
        self._collection = None
        self._content_collection = None
    
    def _get_chroma_collection(self):
        """获取 Chroma 集合"""
        if self._collection is None:
            try:
                import chromadb
                
                chroma_dir = self.memory_dir / "chroma_db"
                client = chromadb.PersistentClient(path=str(chroma_dir))
                
                self._collection = client.get_or_create_collection(
                    name="user_analysis",
                    metadata={"hnsw:space": "cosine"}
                )
            except ImportError:
                pass
        
        return self._collection
    
    def _get_content_collection(self):
        """获取内容交互 Chroma 集合"""
        if self._content_collection is None:
            try:
                import chromadb
                
                chroma_dir = self.memory_dir / "chroma_db"
                client = chromadb.PersistentClient(path=str(chroma_dir))
                
                self._content_collection = client.get_or_create_collection(
                    name="content_interactions",
                    metadata={"hnsw:space": "cosine"}
                )
            except ImportError:
                pass
        
        return self._content_collection
    
    def save_result(self, result: AnalysisResult) -> None:
        """保存分析结果"""
        self._save_to_file(result)
        self._save_to_chroma(result)
    
    def _save_to_file(self, result: AnalysisResult) -> None:
        """保存到 JSONL 文件"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.analysis_dir / f"{date_str}.jsonl"
        
        with open(file_path, "a", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False)
            f.write("\n")
    
    def _save_to_chroma(self, result: AnalysisResult) -> None:
        """保存到 Chroma"""
        collection = self._get_chroma_collection()
        if collection is None:
            return
        
        metadata = {
            "timestamp": result.timestamp,
        }
        
        for dim_id, dim_value in result.dimensions.items():
            simple_key = dim_id.replace(".", "_")
            
            if isinstance(dim_value.value, (str, int, float, bool)):
                metadata[simple_key] = dim_value.value
            elif isinstance(dim_value.value, list):
                metadata[simple_key] = json.dumps(dim_value.value, ensure_ascii=False)
            else:
                metadata[simple_key] = json.dumps(dim_value.value, ensure_ascii=False)
            
            metadata[f"{simple_key}_confidence"] = dim_value.confidence
        
        try:
            collection.add(
                ids=[result.result_id],
                documents=[result.message_content],
                metadatas=[metadata],
            )
        except Exception as e:
            print(f"[FlexibleStore] Chroma 保存失败: {e}")
    
    def get_results(self, days: int = 7, limit: Optional[int] = None) -> List[AnalysisResult]:
        """获取历史分析结果"""
        results = []
        
        from datetime import timedelta
        
        for day_offset in range(days):
            date = datetime.now() - timedelta(days=day_offset)
            date_str = date.strftime("%Y-%m-%d")
            
            file_path = self.analysis_dir / f"{date_str}.jsonl"
            
            if not file_path.exists():
                continue
            
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        results.append(AnalysisResult.from_dict(data))
                    except:
                        continue
        
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        if limit:
            results = results[:limit]
        
        return results
    
    def query_by_dimension(
        self,
        dimension_id: str,
        value: Any,
        days: int = 30,
    ) -> List[AnalysisResult]:
        """按维度值查询"""
        collection = self._get_chroma_collection()
        if collection is None:
            return []
        
        simple_key = dimension_id.replace(".", "_")
        
        where_clause = {simple_key: value}
        
        try:
            results = collection.query(
                query_texts=[""],
                where=where_clause,
                n_results=100,
            )
            
            analysis_results = []
            for result_id in results.get("ids", [[]])[0]:
                result = self._load_result_by_id(result_id)
                if result:
                    analysis_results.append(result)
            
            return analysis_results
            
        except Exception as e:
            print(f"[FlexibleStore] 查询失败: {e}")
            return []
    
    def _load_result_by_id(self, result_id: str) -> Optional[AnalysisResult]:
        """通过 ID 加载结果"""
        for file_path in self.analysis_dir.glob("*.jsonl"):
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get("result_id") == result_id:
                            return AnalysisResult.from_dict(data)
                    except:
                        continue
        
        return None
    
    def get_dimension_statistics(
        self,
        dimension_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """获取维度统计信息"""
        results = self.get_results(days)
        
        values = []
        for result in results:
            dim = result.get_dimension(dimension_id)
            if dim:
                values.append(dim.value)
        
        if not values:
            return {"count": 0}
        
        value_counts = {}
        for v in values:
            key = str(v)
            value_counts[key] = value_counts.get(key, 0) + 1
        
        return {
            "count": len(values),
            "unique_values": len(value_counts),
            "value_distribution": value_counts,
            "most_common": max(value_counts.items(), key=lambda x: x[1])[0] if value_counts else None,
        }
    
    def search_by_text(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """文本语义搜索"""
        collection = self._get_chroma_collection()
        if collection is None:
            return []
        
        try:
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
            )
            
            output = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                metadata = results.get("metadatas", [[]])[0][i]
                output.append({
                    "document": doc,
                    "metadata": metadata,
                    "distance": results.get("distances", [[]])[0][i],
                })
            
            return output
            
        except Exception as e:
            print(f"[FlexibleStore] 搜索失败: {e}")
            return []

    # ===== 内容交互事件方法 =====

    def record_content_interaction(self, event: ContentInteractionEvent) -> None:
        """记录内容交互事件"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.content_interactions_dir / f"{date_str}.jsonl"
        
        with open(file_path, "a", encoding="utf-8") as f:
            json.dump(event.to_dict(), f, ensure_ascii=False)
            f.write("\n")
        
        self._save_content_event_to_chroma(event)
    
    def _save_content_event_to_chroma(self, event: ContentInteractionEvent) -> None:
        """保存内容事件到 Chroma"""
        collection = self._get_content_collection()
        if collection is None:
            return
        
        metadata = {
            "content_id": event.content_id,
            "source": event.source,
            "topics": json.dumps(event.topics, ensure_ascii=False),
            "actions": json.dumps(event.actions, ensure_ascii=False),
            "user_rating": event.user_rating if event.user_rating else -1,
            "timestamp": event.timestamp,
        }
        
        try:
            collection.add(
                ids=[event.event_id],
                documents=[event.title],
                metadatas=[metadata],
            )
        except Exception as e:
            print(f"[FlexibleStore] 内容事件 Chroma 保存失败: {e}")
    
    def get_content_interactions(
        self,
        days: int = 30,
        source: Optional[str] = None,
    ) -> List[ContentInteractionEvent]:
        """获取内容交互历史"""
        events = []
        
        from datetime import timedelta
        
        for day_offset in range(days):
            date = datetime.now() - timedelta(days=day_offset)
            date_str = date.strftime("%Y-%m-%d")
            
            file_path = self.content_interactions_dir / f"{date_str}.jsonl"
            
            if not file_path.exists():
                continue
            
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        event = ContentInteractionEvent.from_dict(data)
                        if source and event.source != source:
                            continue
                        events.append(event)
                    except:
                        continue
        
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events
    
    def get_content_interaction_stats(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """获取内容交互统计"""
        events = self.get_content_interactions(days)
        
        if not events:
            return {"total": 0}
        
        topic_counts = {}
        for e in events:
            for topic in e.topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        action_counts = {}
        for e in events:
            for action in e.actions:
                action_counts[action] = action_counts.get(action, 0) + 1
        
        source_counts = {}
        for e in events:
            source_counts[e.source] = source_counts.get(e.source, 0) + 1
        
        ratings = [e.user_rating for e in events if e.user_rating]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        return {
            "total": len(events),
            "topic_distribution": sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "action_distribution": action_counts,
            "source_distribution": source_counts,
            "avg_rating": round(avg_rating, 2),
            "rating_count": len(ratings),
        }


# 全局存储
_flexible_store: Optional[FlexibleStore] = None


def get_flexible_store(memory_dir: Optional[Path] = None) -> FlexibleStore:
    """获取全局灵活存储"""
    global _flexible_store
    if _flexible_store is None:
        _flexible_store = FlexibleStore(memory_dir)
    return _flexible_store
