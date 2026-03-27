"""X (Twitter) 数据源"""

import os
import asyncio
from datetime import datetime
from typing import List, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from .base import BaseSource
from ..models import ContentItem, ContentSource, ContentStatus


class XSource(BaseSource):
    """X (Twitter) 数据源
    
    使用 Twitter API v2 获取推文
    """
    
    source_type = ContentSource.X
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.bearer_token = self.config.get("bearer_token") or os.getenv("X_BEARER_TOKEN")
        self.api_base = "https://api.twitter.com/2"
        
    async def fetch(
        self,
        since: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[ContentItem]:
        """获取推文
        
        注意: 这里使用简化实现，实际应调用 Twitter API
        """
        if not HAS_HTTPX:
            print("[XSource] httpx not installed, skipping")
            return []
            
        if not self.bearer_token:
            print("[XSource] No bearer token configured")
            return []
        
        # TODO: 实现真实的 Twitter API 调用
        # 这里返回示例数据用于测试
        return self._get_mock_data(limit)
    
    def _get_mock_data(self, limit: int) -> List[ContentItem]:
        """获取示例数据"""
        samples = [
            {
                "id": "123456",
                "author": "naval",
                "content": "The purpose of life is not to be happy. It is to be useful, to be honorable, to be compassionate, to have it make some difference that you have lived and lived well.",
                "url": "https://twitter.com/naval/status/123456",
            },
            {
                "id": "234567",
                "author": "paulg",
                "content": "Startups die because they lose focus, not because they run out of money. Money is just a symptom of losing focus.",
                "url": "https://twitter.com/paulg/status/234567",
            },
            {
                "id": "345678",
                "author": "sama",
                "content": "AI is the most important technology humanity has ever developed. It will change everything about how we live and work.",
                "url": "https://twitter.com/sama/status/345678",
            },
        ]
        
        items = []
        for i, data in enumerate(samples[:limit]):
            item = ContentItem(
                id=self._generate_id(data["id"]),
                source=ContentSource.X,
                title=f"Tweet by @{data['author']}",
                content=data["content"],
                url=data["url"],
                author=data["author"],
                status=ContentStatus.RAW,
            )
            items.append(item)
        
        return items
    
    async def health_check(self) -> bool:
        """检查 API 状态"""
        if not self.bearer_token:
            return False
        return True


class XMockSource(XSource):
    """X 模拟数据源 (用于测试)"""
    
    async def fetch(
        self,
        since: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[ContentItem]:
        """返回模拟数据"""
        await asyncio.sleep(0.1)  # 模拟网络延迟
        return self._get_mock_data(limit)
