"""内容流水线数据模型"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class ContentSource(Enum):
    """内容来源"""
    X = "x"
    RSS = "rss"
    MANUAL = "manual"


class ContentStatus(Enum):
    """内容处理状态"""
    RAW = "raw"           # 原始采集
    SUMMARIZED = "summarized"  # 已摘要
    TRANSLATED = "translated"  # 已翻译
    READY = "ready"       # 可发布
    PUBLISHED = "published"   # 已发布
    FAILED = "failed"     # 处理失败


class PlatformType(Enum):
    """目标平台"""
    XIAOHONGSHU = "xiaohongshu"


@dataclass
class ContentItem:
    """内容条目"""
    id: str
    source: ContentSource
    title: str
    content: str
    url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    status: ContentStatus = ContentStatus.RAW
    
    # 处理结果
    summary: Optional[str] = None
    translated_content: Optional[str] = None
    
    # 小红书格式
    xiaohongshu_content: Optional[str] = None
    xiaohongshu_tags: List[str] = field(default_factory=list)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PipelineResult:
    """流水线处理结果"""
    item: ContentItem
    success: bool
    stage: str
    error: Optional[str] = None
    processed_at: datetime = field(default_factory=datetime.now)


@dataclass
class XiaoHongShuPost:
    """小红书发布内容"""
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)  # 图片路径
    original_url: Optional[str] = None
