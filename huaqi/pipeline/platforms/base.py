"""平台发布基类"""

from abc import ABC, abstractmethod
from typing import Optional

from ..models import ContentItem


class BasePublisher(ABC):
    """内容发布平台基类"""
    
    platform_name: str = "base"
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    @abstractmethod
    async def publish(self, item: ContentItem) -> bool:
        """发布内容
        
        Args:
            item: 内容条目
            
        Returns:
            是否发布成功
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """检查平台连接状态"""
        pass
    
    async def preview(self, item: ContentItem) -> str:
        """预览发布内容"""
        return item.xiaohongshu_content or item.content
