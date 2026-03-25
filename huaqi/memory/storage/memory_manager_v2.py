"""新一代记忆管理器

纯 LLM + 算法实现，无需 Embedding 模型
兼容所有大模型
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import json

from ..search.hybrid_search import HybridSearch, HybridSearchResult
from ..search.text_search import TextSearch
from ..search.llm_search import LLMRelevanceSearch
from .markdown_store import MarkdownMemoryStore


class MemoryManagerV2:
    """记忆管理器 V2
    
    特点：
    - 无需 Embedding 模型
    - 支持所有 LLM（只要会对话）
    - 混合搜索：BM25 + LLM 相关性判断
    - 纯本地算法 + LLM API
    """
    
    def __init__(self, data_dir: Path, user_id: str, llm_manager=None):
        self.data_dir = Path(data_dir)
        self.user_id = user_id
        self.llm_manager = llm_manager
        
        # 目录结构
        self.memory_dir = self.data_dir / "users_data" / user_id / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 搜索引擎
        self.search_engine: Optional[HybridSearch] = None
        if llm_manager:
            self.search_engine = HybridSearch(llm_manager, text_algorithm="bm25")
        
        # Markdown 存储
        self.markdown_store = MarkdownMemoryStore(self.memory_dir)
        
        # 索引状态
        self._indexed_files: set = set()
    
    def add_memory(
        self,
        content: str,
        memory_type: str = "note",
        metadata: Dict[str, Any] = None
    ) -> Path:
        """添加记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型 (identity/project/skill/note/insight)
            metadata: 元数据
            
        Returns:
            Path: 保存的文件路径
        """
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{memory_type}_{timestamp}.md"
        
        # 构建 Markdown 内容
        md_content = self._build_memory_markdown(
            content=content,
            memory_type=memory_type,
            metadata=metadata
        )
        
        # 保存到文件
        filepath = self.memory_dir / memory_type / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        # 添加到搜索索引（如果启用了搜索）
        if self.search_engine:
            self.search_engine.add_document(
                content=content,
                metadata={
                    "type": memory_type,
                    "filepath": str(filepath),
                    **(metadata or {})
                }
            )
        
        return filepath
    
    def _build_memory_markdown(
        self,
        content: str,
        memory_type: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """构建记忆 Markdown"""
        timestamp = datetime.now().isoformat()
        
        lines = [
            "---",
            f"type: {memory_type}",
            f"created_at: {timestamp}",
        ]
        
        # 添加元数据
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    lines.append(f"{key}: {value}")
        
        lines.extend([
            "---",
            "",
            f"# {memory_type.title()} 记忆",
            "",
            content,
            "",
        ])
        
        return "\n".join(lines)
    
    def search(
        self,
        query: str,
        search_type: str = "hybrid",
        top_k: int = 5,
        memory_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """搜索记忆
        
        Args:
            query: 查询文本
            search_type: 搜索类型 (hybrid/text/llm)
            top_k: 返回数量
            memory_type: 按类型过滤
            
        Returns:
            List[Dict]: 搜索结果
        """
        if not query.strip():
            return []
        
        # 如果没有 LLM，回退到文本搜索
        if not self.search_engine or not self.llm_manager:
            return self._text_search_only(query, top_k, memory_type)
        
        # 确保索引已构建
        if not self._indexed_files:
            self._build_index()
        
        # 执行搜索
        if search_type == "text":
            # 纯文本搜索
            text_search = TextSearch("bm25")
            self._load_all_memories_into_search(text_search, memory_type)
            results = text_search.search(query, top_k)
            
            return [
                {
                    "content": r.content,
                    "score": r.score,
                    "matched_terms": r.matched_terms,
                    "metadata": r.metadata,
                    "search_method": "bm25"
                }
                for r in results
            ]
        
        elif search_type == "llm":
            # 纯 LLM 搜索
            memories = self._load_all_memories(memory_type)
            llm_search = LLMRelevanceSearch(self.llm_manager)
            results = llm_search.search(query, memories, top_k)
            
            return [
                {
                    "content": r.content,
                    "score": r.score,
                    "reason": r.reason,
                    "metadata": r.metadata,
                    "search_method": "llm"
                }
                for r in results
            ]
        
        else:
            # 混合搜索（默认）
            results = self.search_engine.search(query, top_k=top_k)
            
            # 按类型过滤
            if memory_type:
                results = [r for r in results 
                          if r.metadata.get("type") == memory_type]
            
            return [
                {
                    "content": r.content,
                    "score": r.score,
                    "text_score": r.text_score,
                    "llm_score": r.llm_score,
                    "source": r.source,
                    "metadata": r.metadata,
                    "search_method": "hybrid"
                }
                for r in results
            ]
    
    def _text_search_only(
        self,
        query: str,
        top_k: int,
        memory_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """纯文本搜索（无 LLM）"""
        text_search = TextSearch("bm25")
        self._load_all_memories_into_search(text_search, memory_type)
        
        results = text_search.search(query, top_k)
        
        return [
            {
                "content": r.content,
                "score": r.score,
                "matched_terms": r.matched_terms,
                "metadata": r.metadata,
                "search_method": "bm25"
            }
            for r in results
        ]
    
    def _load_all_memories(self, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """加载所有记忆"""
        memories = []
        
        search_dir = self.memory_dir
        if memory_type:
            search_dir = search_dir / memory_type
        
        if not search_dir.exists():
            return memories
        
        for md_file in search_dir.rglob("*.md"):
            try:
                content = self.markdown_store.load_conversation(md_file)
                if content:
                    # 提取正文（去掉 frontmatter）
                    body = self._extract_body(md_file.read_text())
                    memories.append({
                        "content": body,
                        "metadata": {
                            "filepath": str(md_file),
                            "type": content.get("type", "unknown"),
                        }
                    })
            except:
                continue
        
        return memories
    
    def _load_all_memories_into_search(
        self,
        search_engine: Union[TextSearch, HybridSearch],
        memory_type: Optional[str] = None
    ):
        """加载所有记忆到搜索引擎"""
        memories = self._load_all_memories(memory_type)
        
        for mem in memories:
            search_engine.add_document(
                content=mem["content"],
                metadata=mem["metadata"]
            )
    
    def _extract_body(self, content: str) -> str:
        """提取 Markdown 正文"""
        # 移除 frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]
        
        return content.strip()
    
    def _build_index(self):
        """构建搜索索引"""
        if not self.search_engine:
            return
        
        print(f"[{self.user_id}] 构建记忆索引...")
        
        memories = self._load_all_memories()
        
        for mem in memories:
            self.search_engine.add_document(
                content=mem["content"],
                metadata=mem["metadata"]
            )
        
        self._indexed_files = {m["metadata"]["filepath"] for m in memories}
        
        print(f"[{self.user_id}] 索引完成: {len(memories)} 条记忆")
    
    def list_memories(self, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有记忆"""
        memories = []
        
        search_dir = self.memory_dir
        if memory_type:
            search_dir = search_dir / memory_type
        
        if not search_dir.exists():
            return memories
        
        for md_file in search_dir.rglob("*.md"):
            try:
                stat = md_file.stat()
                memories.append({
                    "path": str(md_file.relative_to(self.memory_dir)),
                    "type": memory_type or md_file.parent.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except:
                continue
        
        return sorted(memories, key=lambda x: x["modified"], reverse=True)
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        stats = {
            "total_files": 0,
            "by_type": {},
            "total_size_bytes": 0,
        }
        
        for md_file in self.memory_dir.rglob("*.md"):
            try:
                stat = md_file.stat()
                mem_type = md_file.parent.name
                
                stats["total_files"] += 1
                stats["total_size_bytes"] += stat.st_size
                stats["by_type"][mem_type] = stats["by_type"].get(mem_type, 0) + 1
            except:
                continue
        
        # 人类可读的大小
        size_mb = stats["total_size_bytes"] / 1024 / 1024
        stats["total_size_human"] = f"{size_mb:.2f} MB"
        
        return stats
    
    def delete_memory(self, filepath: Union[str, Path]) -> bool:
        """删除记忆"""
        if isinstance(filepath, str):
            filepath = self.memory_dir / filepath
        else:
            filepath = self.memory_dir / filepath
        
        if filepath.exists() and filepath.is_file():
            filepath.unlink()
            return True
        return False
    
    def export_memories(self, output_dir: Path, memory_type: Optional[str] = None):
        """导出记忆"""
        from shutil import copytree
        
        source_dir = self.memory_dir
        if memory_type:
            source_dir = source_dir / memory_type
        
        if source_dir.exists():
            copytree(source_dir, output_dir, dirs_exist_ok=True)
            return True
        return False
