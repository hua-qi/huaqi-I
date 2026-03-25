"""向量存储系统

基于 Chroma 的语义检索
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import hashlib
import json


@dataclass
class VectorDocument:
    """向量文档"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


class EmbeddingProvider:
    """Embedding 提供商基类"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
    
    def embed(self, text: str) -> List[float]:
        """生成文本的向量嵌入"""
        raise NotImplementedError
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成向量嵌入"""
        return [self.embed(text) for text in texts]


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI Embedding"""
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        super().__init__(api_key)
        self.model = model
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=self.api_key)
        return self._client
    
    def embed(self, text: str) -> List[float]:
        try:
            client = self._get_client()
            response = client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise VectorStoreError(f"Embedding 生成失败: {e}")
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            client = self._get_client()
            response = client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise VectorStoreError(f"批量 Embedding 生成失败: {e}")


class LocalEmbedding(EmbeddingProvider):
    """本地 Embedding（使用 sentence-transformers）"""
    
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self._model = None
    
    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                raise VectorStoreError(
                    "请先安装 sentence-transformers: pip install sentence-transformers"
                )
        return self._model
    
    def embed(self, text: str) -> List[float]:
        model = self._get_model()
        embedding = model.encode(text)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        embeddings = model.encode(texts)
        return embeddings.tolist()


class DummyEmbedding(EmbeddingProvider):
    """虚拟 Embedding（用于测试）"""
    
    def embed(self, text: str) -> List[float]:
        # 返回固定长度的随机向量
        import random
        random.seed(hash(text))
        return [random.random() for _ in range(384)]
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(text) for text in texts]


class VectorStore:
    """向量存储
    
    基于 Chroma 的语义检索系统
    """
    
    def __init__(
        self,
        persist_directory: Path,
        embedding_provider: Optional[EmbeddingProvider] = None,
        collection_name: str = "memories"
    ):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_provider = embedding_provider or DummyEmbedding()
        self.collection_name = collection_name
        
        self._client = None
        self._collection = None
    
    def _get_client(self):
        """获取或创建 Chroma 客户端"""
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_directory)
                )
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except ImportError:
                raise VectorStoreError("请先安装 chromadb: pip install chromadb")
        return self._client
    
    def _get_collection(self):
        """获取集合"""
        if self._collection is None:
            self._get_client()
        return self._collection
    
    def add_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """添加文档到向量库
        
        Args:
            content: 文档内容
            metadata: 元数据
            doc_id: 文档ID（可选）
            
        Returns:
            str: 文档ID
        """
        collection = self._get_collection()
        
        # 生成文档ID
        if doc_id is None:
            doc_id = hashlib.md5(content.encode()).hexdigest()[:16]
        
        # 生成向量
        embedding = self.embedding_provider.embed(content)
        
        # 添加文档
        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata or {}]
        )
        
        return doc_id
    
    def add_documents(self, documents: List[VectorDocument]) -> List[str]:
        """批量添加文档
        
        Args:
            documents: 文档列表
            
        Returns:
            List[str]: 文档ID列表
        """
        if not documents:
            return []
        
        collection = self._get_collection()
        
        # 准备数据
        ids = [doc.id for doc in documents]
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        
        # 批量生成向量
        embeddings = self.embedding_provider.embed_batch(contents)
        
        # 添加文档
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas
        )
        
        return ids
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """语义搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_dict: 过滤条件
            
        Returns:
            List[Dict]: 搜索结果
        """
        collection = self._get_collection()
        
        # 生成查询向量
        query_embedding = self.embedding_provider.embed(query)
        
        # 执行搜索
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_dict,
            include=["documents", "metadatas", "distances"]
        )
        
        # 格式化结果
        formatted_results = []
        for i in range(len(results["ids"][0])):
            formatted_results.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "score": 1 - results["distances"][0][i],  # 转换为相似度分数
            })
        
        return formatted_results
    
    def delete(self, doc_id: str) -> bool:
        """删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            bool: 是否成功
        """
        collection = self._get_collection()
        try:
            collection.delete(ids=[doc_id])
            return True
        except:
            return False
    
    def update(
        self,
        doc_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新文档
        
        Args:
            doc_id: 文档ID
            content: 新内容（可选）
            metadata: 新元数据（可选）
            
        Returns:
            bool: 是否成功
        """
        collection = self._get_collection()
        
        try:
            update_data = {}
            if content is not None:
                update_data["documents"] = [content]
                update_data["embeddings"] = [self.embedding_provider.embed(content)]
            if metadata is not None:
                update_data["metadatas"] = [metadata]
            
            if update_data:
                collection.update(
                    ids=[doc_id],
                    **update_data
                )
            return True
        except:
            return False
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取单个文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            Dict: 文档信息
        """
        collection = self._get_collection()
        
        try:
            result = collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )
            
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "content": result["documents"][0],
                    "metadata": result["metadatas"][0],
                }
            return None
        except:
            return None
    
    def count(self) -> int:
        """获取文档数量"""
        collection = self._get_collection()
        return collection.count()
    
    def clear(self):
        """清空所有文档（危险操作！）"""
        collection = self._get_collection()
        collection.delete()


class UserVectorStore:
    """用户隔离的向量存储
    
    每个用户独立的向量库
    """
    
    def __init__(self, base_dir: Path, user_id: str, embedding_provider: Optional[EmbeddingProvider] = None):
        self.user_id = user_id
        self.vector_dir = base_dir / "users_data" / user_id / "vectors"
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        
        self.store = VectorStore(
            persist_directory=self.vector_dir,
            embedding_provider=embedding_provider,
            collection_name=f"user_{user_id}"
        )
    
    def index_markdown_file(self, filepath: Path, metadata: Optional[Dict] = None):
        """索引 Markdown 文件
        
        将 Markdown 文件分块并添加到向量库
        """
        if not filepath.exists():
            return
        
        # 读取内容
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 解析 frontmatter
        from .markdown_store import MarkdownMemoryStore
        store = MarkdownMemoryStore(Path("/tmp"))  # 临时实例用于解析
        frontmatter, body = store._parse_frontmatter(content)
        
        # 分块（简单实现：按段落分割）
        chunks = self._chunk_text(body)
        
        # 添加到向量库
        documents = []
        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 50:  # 跳过太短的块
                continue
            
            doc_id = f"{filepath.stem}_{i}"
            doc_metadata = {
                "source": str(filepath),
                "chunk_index": i,
                "type": frontmatter.get("type", "unknown"),
                **(metadata or {})
            }
            
            documents.append(VectorDocument(
                id=doc_id,
                content=chunk,
                metadata=doc_metadata
            ))
        
        if documents:
            self.store.add_documents(documents)
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """文本分块
        
        Args:
            text: 原始文本
            chunk_size: 每块大小（字符数）
            overlap: 重叠大小
            
        Returns:
            List[str]: 文本块列表
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # 尝试在句子边界截断
            if end < len(text):
                # 查找最近的句号、问号、感叹号或换行
                for sep in [".", "?", "!", "\n"]:
                    last_sep = chunk.rfind(sep)
                    if last_sep > chunk_size // 2:  # 至少保留一半内容
                        chunk = chunk[:last_sep + 1]
                        break
            
            chunks.append(chunk.strip())
            start += len(chunk) - overlap
        
        return chunks
    
    def search_memories(self, query: str, memory_type: Optional[str] = None, top_k: int = 5) -> List[Dict]:
        """搜索用户记忆
        
        Args:
            query: 查询文本
            memory_type: 记忆类型过滤
            top_k: 返回数量
            
        Returns:
            List[Dict]: 搜索结果
        """
        filter_dict = None
        if memory_type:
            filter_dict = {"type": memory_type}
        
        return self.store.search(query, top_k=top_k, filter_dict=filter_dict)
    
    def index_all_memories(self, memory_dir: Path):
        """索引所有记忆文件"""
        for md_file in memory_dir.rglob("*.md"):
            try:
                self.index_markdown_file(md_file)
            except Exception as e:
                print(f"索引失败 {md_file}: {e}")


class VectorStoreError(Exception):
    """向量存储错误"""
    pass
