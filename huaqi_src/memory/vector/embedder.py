"""Embedding 服务 - 封装 sentence-transformers"""

from pathlib import Path
from typing import List, Optional, Union

import numpy as np


class EmbeddingService:
    """Embedding 服务 - 文本向量化
    
    支持多种模型：
    - BAAI/bge-small-zh (默认，轻量中文)
    - BAAI/bge-large-zh (高质量中文)
    - sentence-transformers/all-MiniLM-L6-v2 (英文)
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh",
        device: str = "auto",
        normalize_embeddings: bool = True,
        cache_dir: Optional[Union[str, Path]] = None,
    ):
        """初始化 Embedding 服务
        
        Args:
            model_name: 模型名称，默认使用 BGE-small-zh
            device: 计算设备 (auto/cpu/cuda/mps)
            normalize_embeddings: 是否归一化向量
            cache_dir: 模型缓存目录
        """
        self.model_name = model_name
        self.device = self._resolve_device(device)
        self.normalize_embeddings = normalize_embeddings
        
        if cache_dir is None:
            from ...core.config_paths import get_models_cache_dir
            cache_dir = get_models_cache_dir()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._model = None
    
    def _resolve_device(self, device: str) -> str:
        """解析设备"""
        if device != "auto":
            return device
        
        # 自动检测最优设备
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        
        return "cpu"
    
    @property
    def model(self):
        """延迟加载模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                print(f"正在加载 embedding 模型: {self.model_name}...")
                self._model = SentenceTransformer(
                    self.model_name,
                    device=self.device,
                    cache_folder=str(self.cache_dir),
                )
                print(f"模型加载完成，维度: {self.dimension}")
                
            except ImportError:
                raise ImportError(
                    "请先安装 sentence-transformers: "
                    "pip install sentence-transformers"
                )
        return self._model
    
    @property
    def dimension(self) -> int:
        """获取向量维度"""
        if self._model is None:
            # 常见模型维度
            dims = {
                "bge-small": 512,
                "bge-base": 768,
                "bge-large": 1024,
                "MiniLM": 384,
            }
            for key, dim in dims.items():
                if key.lower() in self.model_name.lower():
                    return dim
            return 768  # 默认值
        return self._model.get_sentence_embedding_dimension()
    
    def embed(self, text: str) -> List[float]:
        """将单个文本转为向量
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表
        """
        if not text or not text.strip():
            return [0.0] * self.dimension
        
        embedding = self.model.encode(
            text,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
        )
        return embedding.tolist()
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """批量编码文本
        
        Args:
            texts: 文本列表
            batch_size: 批处理大小
            show_progress: 是否显示进度条
            
        Returns:
            向量列表
        """
        if not texts:
            return []
        
        # 过滤空文本
        valid_texts = [t if t and t.strip() else "" for t in texts]
        
        embeddings = self.model.encode(
            valid_texts,
            batch_size=batch_size,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=show_progress and len(texts) > 100,
            convert_to_numpy=True,
        )
        
        return embeddings.tolist()
    
    def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """计算两个向量的余弦相似度
        
        Args:
            embedding1: 向量1
            embedding2: 向量2
            
        Returns:
            相似度分数 (0-1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # 余弦相似度
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
    ) -> List[tuple]:
        """使用向量相似度重新排序文档
        
        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前 k 个结果
            
        Returns:
            [(文档索引, 相似度), ...]
        """
        if not documents:
            return []
        
        query_embedding = self.embed(query)
        doc_embeddings = self.embed_batch(documents)
        
        similarities = [
            (i, self.compute_similarity(query_embedding, doc_emb))
            for i, doc_emb in enumerate(doc_embeddings)
        ]
        
        # 按相似度降序排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        if top_k:
            similarities = similarities[:top_k]
        
        return similarities


# 单例
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(
    model_name: str = "BAAI/bge-small-zh",
    device: str = "auto",
) -> EmbeddingService:
    """获取 Embedding 服务单例"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(
            model_name=model_name,
            device=device,
        )
    return _embedding_service
