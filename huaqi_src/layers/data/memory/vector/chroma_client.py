"""Chroma 向量数据库客户端封装"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings


class ChromaClient:
    """Chroma 向量数据库客户端
    
    提供封装好的向量存储和检索功能：
    - 集合创建和管理
    - 文档添加和更新
    - 向量搜索 (相似度)
    """
    
    def __init__(
        self,
        persist_directory: Optional[Union[str, Path]] = None,
        collection_name: str = "memories",
        embedding_function: Optional[Any] = None,
    ):
        """初始化 Chroma 客户端
        
        Args:
            persist_directory: 数据持久化目录，默认为 ~/.huaqi/vector_db
            collection_name: 集合名称
            embedding_function: 可选的自定义 embedding 函数
        """
        if persist_directory is None:
            from ...config.paths import get_vector_db_dir
            persist_directory = get_vector_db_dir()
        
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # 设置环境变量禁用 Chroma 自动下载 embedding 模型
        os.environ.setdefault("CHROMA_DEFAULT_EMBEDDING_FUNCTION", "none")
        
        # 创建客户端
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
        
        self.collection_name = collection_name
        self._embedding_function = embedding_function
        self._collection: Optional[Collection] = None
    
    @property
    def collection(self) -> Collection:
        """获取或创建集合"""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedding_function,
                metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
            )
        return self._collection
    
    def add(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> bool:
        """添加文档到向量库
        
        Args:
            doc_id: 文档唯一ID
            content: 文档内容
            metadata: 元数据 (如 date, type, tags)
            embedding: 可选的预计算向量
            
        Returns:
            bool: 是否成功
        """
        try:
            self.collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata or {}],
                embeddings=[embedding] if embedding else None,
            )
            return True
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False
    
    def add_batch(
        self,
        doc_ids: List[str],
        contents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> bool:
        """批量添加文档
        
        Args:
            doc_ids: 文档ID列表
            contents: 内容列表
            metadatas: 元数据列表
            embeddings: 预计算向量列表
        """
        try:
            self.collection.add(
                ids=doc_ids,
                documents=contents,
                metadatas=metadatas or [{}] * len(doc_ids),
                embeddings=embeddings,
            )
            return True
        except Exception as e:
            print(f"批量添加失败: {e}")
            return False
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        include_embeddings: bool = False,
    ) -> List[Dict[str, Any]]:
        """向量搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            where: 过滤条件 (如 {"type": "diary"})
            include_embeddings: 是否返回向量
            
        Returns:
            搜索结果列表，包含 id, content, metadata, distance
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where,
                include=["metadatas", "documents", "distances"] + 
                       (["embeddings"] if include_embeddings else []),
            )
            
            # 格式化结果
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    **({"embedding": results["embeddings"][0][i]} 
                       if include_embeddings else {}),
                })
            
            return formatted_results
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
    
    def search_by_vector(
        self,
        embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """使用向量进行搜索
        
        Args:
            embedding: 查询向量
            top_k: 返回结果数量
            where: 过滤条件
        """
        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where=where,
                include=["metadatas", "documents", "distances"],
            )
            
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                })
            
            return formatted_results
        except Exception as e:
            print(f"向量搜索失败: {e}")
            return []
    
    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取指定文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            文档信息或 None
        """
        try:
            result = self.collection.get(
                ids=[doc_id],
                include=["metadatas", "documents"],
            )
            
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "content": result["documents"][0],
                    "metadata": result["metadatas"][0],
                }
            return None
        except Exception as e:
            print(f"获取文档失败: {e}")
            return None
    
    def delete(self, doc_id: str) -> bool:
        """删除文档
        
        Args:
            doc_id: 文档ID
        """
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            print(f"删除失败: {e}")
            return False
    
    def update(
        self,
        doc_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """更新文档
        
        Args:
            doc_id: 文档ID
            content: 新内容
            metadata: 新元数据
        """
        try:
            update_data = {"ids": [doc_id]}
            if content:
                update_data["documents"] = [content]
            if metadata:
                update_data["metadatas"] = [metadata]
            
            self.collection.update(**update_data)
            return True
        except Exception as e:
            print(f"更新失败: {e}")
            return False
    
    def count(self) -> int:
        """获取文档总数"""
        return self.collection.count()
    
    def export_all(self) -> List[Dict[str, Any]]:
        """导出所有文档 (用于迁移)"""
        try:
            results = self.collection.get(
                include=["metadatas", "documents"],
            )
            
            return [
                {
                    "id": results["ids"][i],
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i],
                }
                for i in range(len(results["ids"]))
            ]
        except Exception as e:
            print(f"导出失败: {e}")
            return []
    
    def clear(self) -> bool:
        """清空集合"""
        try:
            self.client.delete_collection(self.collection_name)
            self._collection = None
            return True
        except Exception as e:
            print(f"清空失败: {e}")
            return False


# 单例模式
_chroma_client: Optional[ChromaClient] = None


def get_chroma_client(
    persist_directory: Optional[Union[str, Path]] = None,
    collection_name: str = "memories",
) -> ChromaClient:
    """获取 Chroma 客户端单例"""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = ChromaClient(
            persist_directory=persist_directory,
            collection_name=collection_name,
        )
    return _chroma_client
