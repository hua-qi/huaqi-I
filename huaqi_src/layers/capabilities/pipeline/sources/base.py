"""数据源基类"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from ..models import ContentItem, ContentSource


class BaseSource(ABC):
    """数据源基类"""
    
    source_type: ContentSource
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    @abstractmethod
    async def fetch(
        self,
        since: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[ContentItem]:
        """获取内容
        
        Args:
            since: 从此时间之后的内容
            limit: 最大数量
            
        Returns:
            内容列表
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """检查数据源健康状态"""
        pass
    
    def _generate_id(self, original_id: str) -> str:
        """生成唯一ID"""
        import hashlib
        data = f"{self.source_type.value}_{original_id}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
