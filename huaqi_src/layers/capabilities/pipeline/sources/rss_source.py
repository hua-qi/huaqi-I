"""RSS 数据源"""

import asyncio
from datetime import datetime
from typing import List, Optional

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

from .base import BaseSource
from ..models import ContentItem, ContentSource, ContentStatus


class RSSSource(BaseSource):
    """RSS 数据源"""
    
    source_type = ContentSource.RSS
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.feeds = self.config.get("feeds", [])
        
    async def fetch(
        self,
        since: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[ContentItem]:
        """获取 RSS 内容"""
        if not HAS_FEEDPARSER:
            print("[RSSSource] feedparser not installed, skipping")
            return []
        
        if not self.feeds:
            print("[RSSSource] No RSS feeds configured")
            return []
        
        items = []
        for feed_url in self.feeds[:3]:  # 限制数量
            try:
                feed_items = await self._parse_feed(feed_url, since, limit // len(self.feeds) + 1)
                items.extend(feed_items)
            except Exception as e:
                print(f"[RSSSource] Failed to parse {feed_url}: {e}")
        
        return items[:limit]
    
    async def _parse_feed(
        self,
        feed_url: str,
        since: Optional[datetime],
        limit: int,
    ) -> List[ContentItem]:
        """解析单个 RSS Feed"""
        # 使用线程池执行同步的 feedparser
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(feedparser.parse, feed_url)
            feed = await asyncio.wrap_future(future)
        
        items = []
        for entry in feed.entries[:limit]:
            # 解析发布时间
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            
            # 过滤时间
            if since and published and published < since:
                continue
            
            # 提取内容
            content = entry.get('summary', '') or entry.get('description', '')
            if hasattr(entry, 'content'):
                content = entry.content[0].value
            
            item = ContentItem(
                id=self._generate_id(entry.get('id', entry.link)),
                source=ContentSource.RSS,
                title=entry.get('title', 'Untitled'),
                content=content[:2000],  # 限制长度
                url=entry.get('link'),
                author=feed.feed.get('title'),
                published_at=published,
                status=ContentStatus.RAW,
                metadata={
                    'feed_url': feed_url,
                    'feed_title': feed.feed.get('title'),
                }
            )
            items.append(item)
        
        return items
    
    async def health_check(self) -> bool:
        """检查 RSS 源状态"""
        if not HAS_FEEDPARSER:
            return False
        if not self.feeds:
            return False
        return True


class RSSMockSource(RSSSource):
    """RSS 模拟数据源"""
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        # 预配置一些示例 feeds
        self.feeds = ["https://example.com/feed.xml"]
    
    async def fetch(
        self,
        since: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[ContentItem]:
        """返回模拟数据"""
        await asyncio.sleep(0.1)
        
        samples = [
            {
                "id": "rss_001",
                "title": "2024年AI发展报告：大模型技术突破",
                "content": "今年大语言模型在理解和生成能力上取得了显著进展...",
                "url": "https://example.com/ai-report-2024",
                "author": "科技日报",
            },
            {
                "id": "rss_002",
                "title": "Python 3.13 新特性解析",
                "content": "Python 3.13 带来了性能提升和新语法特性...",
                "url": "https://example.com/python-313",
                "author": "Python Weekly",
            },
            {
                "id": "rss_003",
                "title": "如何建立个人知识管理系统",
                "content": "在信息爆炸的时代，建立有效的知识管理系统至关重要...",
                "url": "https://example.com/knowledge-management",
                "author": "效率工具",
            },
        ]
        
        items = []
        for data in samples[:limit]:
            item = ContentItem(
                id=self._generate_id(data["id"]),
                source=ContentSource.RSS,
                title=data["title"],
                content=data["content"],
                url=data["url"],
                author=data["author"],
                status=ContentStatus.RAW,
            )
            items.append(item)
        
        return items
