"""内容流水线核心

负责协调数据源、处理器和发布平台的完整流程
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import ContentItem, ContentStatus, PipelineResult
from .sources import BaseSource, XMockSource, RSSMockSource
from .processors import BaseProcessor, Summarizer, Translator, XiaoHongShuFormatter
from .platforms import BasePublisher, XiaoHongShuPublisher


class ContentPipeline:
    """内容处理流水线
    
    流程: 采集 -> 摘要 -> 翻译 -> 格式化 -> 发布
    """
    
    def __init__(
        self,
        sources: Optional[List[BaseSource]] = None,
        processors: Optional[List[BaseProcessor]] = None,
        publisher: Optional[BasePublisher] = None,
    ):
        self.sources = sources or []
        self.processors = processors or []
        self.publisher = publisher
        
        # 统计信息
        self.stats = {
            "fetched": 0,
            "processed": 0,
            "published": 0,
            "failed": 0,
        }
    
    async def run(
        self,
        since: Optional[datetime] = None,
        limit: int = 10,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """执行完整流水线
        
        Args:
            since: 只处理此时间之后的内容
            limit: 每个源最大采集数量
            dry_run: 是否只预览不发布
            
        Returns:
            执行统计
        """
        print("=" * 50)
        print("🚀 启动内容流水线")
        print("=" * 50)
        
        # 1. 采集内容
        print("\n📥 步骤 1: 采集内容")
        items = await self._fetch_all(since, limit)
        print(f"   共采集 {len(items)} 条内容")
        
        if not items:
            print("\n⚠️ 没有新内容，流水线结束")
            return self.stats
        
        # 2. 处理内容
        print("\n🔧 步骤 2: 处理内容")
        processed = await self._process_all(items)
        print(f"   处理完成: {len([r for r in processed if r.success])}/{len(processed)}")
        
        # 3. 发布内容
        if self.publisher:
            ready_items = [
                r.item for r in processed
                if r.success and r.item.status == ContentStatus.READY
            ]
            
            if dry_run:
                # 预览模式：保存草稿但不发布
                print("\n📝 步骤 3: [预览模式] 保存草稿")
                await self._publish_all(ready_items, dry_run=True)
            else:
                print("\n📤 步骤 3: 发布内容")
                published = await self._publish_all(ready_items, dry_run=False)
                print(f"   发布完成: {published}/{len(ready_items)}")
        
        # 输出统计
        print("\n" + "=" * 50)
        print("📊 流水线统计")
        print("=" * 50)
        for key, value in self.stats.items():
            print(f"   {key}: {value}")
        
        return self.stats
    
    async def _fetch_all(
        self,
        since: Optional[datetime],
        limit: int,
    ) -> List[ContentItem]:
        """从所有源采集内容"""
        all_items = []
        
        for source in self.sources:
            try:
                items = await source.fetch(since=since, limit=limit)
                all_items.extend(items)
                print(f"   ✓ {source.source_type.value}: {len(items)} 条")
            except Exception as e:
                print(f"   ✗ {source.source_type.value}: 失败 - {e}")
        
        self.stats["fetched"] = len(all_items)
        return all_items
    
    async def _process_all(self, items: List[ContentItem]) -> List[PipelineResult]:
        """处理所有内容"""
        results = []
        
        for item in items:
            result = await self._process_item(item)
            results.append(result)
            
            if result.success:
                self.stats["processed"] += 1
            else:
                self.stats["failed"] += 1
        
        return results
    
    async def _process_item(self, item: ContentItem) -> PipelineResult:
        """处理单个内容"""
        for processor in self.processors:
            try:
                result = await processor.process(item)
                if not result.success:
                    return result
            except Exception as e:
                return PipelineResult(
                    item=item,
                    success=False,
                    stage=processor.name,
                    error=str(e),
                )
        
        return PipelineResult(
            item=item,
            success=True,
            stage="complete",
        )
    
    async def _publish_all(self, items: List[ContentItem], dry_run: bool = False) -> int:
        """发布所有内容
        
        Args:
            items: 内容列表
            dry_run: 如果为 True，只保存草稿不发布
        """
        published = 0
        
        for item in items:
            try:
                # 检查 publisher 是否支持 dry_run 参数
                if hasattr(self.publisher, 'publish') and 'dry_run' in self.publisher.publish.__code__.co_varnames:
                    if await self.publisher.publish(item, dry_run=dry_run):
                        published += 1
                        if not dry_run:
                            self.stats["published"] += 1
                else:
                    # 不支持 dry_run 的 publisher
                    if not dry_run:
                        if await self.publisher.publish(item):
                            published += 1
                            self.stats["published"] += 1
            except Exception as e:
                print(f"   ✗ 发布失败 [{item.id}]: {e}")
        
        return published
    
    def preview(self, item: ContentItem) -> str:
        """预览内容"""
        return item.xiaohongshu_content or item.content


class PipelineBuilder:
    """流水线构建器"""
    
    def __init__(self):
        self.sources: List[BaseSource] = []
        self.processors: List[BaseProcessor] = []
        self.publisher: Optional[BasePublisher] = None
    
    def add_x_source(self, mock: bool = True, **config) -> "PipelineBuilder":
        """添加 X 数据源"""
        if mock:
            self.sources.append(XMockSource(config))
        else:
            from .sources import XSource
            self.sources.append(XSource(config))
        return self
    
    def add_rss_source(self, mock: bool = True, **config) -> "PipelineBuilder":
        """添加 RSS 数据源"""
        if mock:
            self.sources.append(RSSMockSource(config))
        else:
            from .sources import RSSSource
            self.sources.append(RSSSource(config))
        return self
    
    def add_summarizer(self, max_length: int = 500) -> "PipelineBuilder":
        """添加摘要处理器"""
        self.processors.append(Summarizer(max_length=max_length))
        return self
    
    def add_translator(self, use_llm: bool = True) -> "PipelineBuilder":
        """添加翻译处理器"""
        self.processors.append(Translator(use_llm=use_llm))
        return self
    
    def add_xiaohongshu_formatter(self) -> "PipelineBuilder":
        """添加小红书格式器"""
        self.processors.append(XiaoHongShuFormatter())
        return self
    
    def set_xiaohongshu_publisher(self, **config) -> "PipelineBuilder":
        """设置小红书发布器"""
        self.publisher = XiaoHongShuPublisher(config)
        return self
    
    def build(self) -> ContentPipeline:
        """构建流水线"""
        return ContentPipeline(
            sources=self.sources,
            processors=self.processors,
            publisher=self.publisher,
        )


# 默认流水线配置
def create_default_pipeline(
    draft_dir: Optional[str] = None,
    mock_sources: bool = True,
) -> ContentPipeline:
    """创建默认流水线
    
    默认流程: X/RSS -> 摘要 -> 翻译 -> 小红书格式 -> 草稿
    """
    builder = PipelineBuilder()
    
    # 数据源
    builder.add_x_source(mock=mock_sources)
    builder.add_rss_source(mock=mock_sources)
    
    # 处理器
    builder.add_summarizer(max_length=500)
    builder.add_translator(use_llm=False)  # 简化版本
    builder.add_xiaohongshu_formatter()
    
    # 发布器
    config = {}
    if draft_dir:
        config["draft_dir"] = draft_dir
    builder.set_xiaohongshu_publisher(**config)
    
    return builder.build()
