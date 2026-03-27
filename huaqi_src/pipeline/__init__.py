"""内容流水线模块

支持 X、RSS 等内容源采集，自动摘要、翻译、格式化，
并发布到小红书等平台。

使用示例:
    from huaqi_src.pipeline import create_default_pipeline

    pipeline = create_default_pipeline()
    await pipeline.run(limit=5)
"""

from .models import (
    ContentItem,
    ContentSource,
    ContentStatus,
    PlatformType,
    PipelineResult,
    XiaoHongShuPost,
)
from .core import ContentPipeline, PipelineBuilder, create_default_pipeline

__all__ = [
    "ContentItem",
    "ContentSource",
    "ContentStatus",
    "PlatformType",
    "PipelineResult",
    "XiaoHongShuPost",
    "ContentPipeline",
    "PipelineBuilder",
    "create_default_pipeline",
]
