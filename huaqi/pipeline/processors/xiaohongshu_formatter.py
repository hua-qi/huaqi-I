"""小红书格式转换器"""

import re
from typing import List

from ..models import ContentItem, ContentStatus, PipelineResult, XiaoHongShuPost
from .base import BaseProcessor


class XiaoHongShuFormatter(BaseProcessor):
    """将内容转换为小红书格式"""
    
    name = "xiaohongshu_formatter"
    
    # 小红书相关热门标签
    DEFAULT_TAGS = [
        "#干货分享",
        "#自我提升",
        "#职场成长",
        "#学习方法",
        "#个人成长",
    ]
    
    def __init__(self, max_length: int = 1000):
        self.max_length = max_length
    
    async def process(self, item: ContentItem) -> PipelineResult:
        """格式化为小红书风格"""
        try:
            content = item.translated_content or item.summary or item.content
            
            # 生成标题
            title = self._generate_title(item)
            
            # 格式化正文
            formatted = self._format_body(content)
            
            # 提取/生成标签
            tags = self._generate_tags(item, content)
            
            # 组装小红书内容
            xiaohongshu_text = self._assemble_post(title, formatted, tags, item.url)
            
            item.xiaohongshu_content = xiaohongshu_text
            item.xiaohongshu_tags = tags
            item.status = ContentStatus.READY
            
            return PipelineResult(
                item=item,
                success=True,
                stage=self.name,
            )
            
        except Exception as e:
            return PipelineResult(
                item=item,
                success=False,
                stage=self.name,
                error=str(e),
            )
    
    def _generate_title(self, item: ContentItem) -> str:
        """生成吸引人的标题"""
        original_title = item.title
        
        # 如果是 tweet，提取核心观点作为标题
        if item.source.value == "x":
            # 使用原文前几字 + 评论风格
            content = item.content
            if len(content) > 20:
                return f"💡 {content[:20]}..."
            return f"💡 {content}"
        
        # RSS 文章标题优化
        if original_title:
            # 添加 emoji 增强吸引力
            if not any(emoji in original_title for emoji in ["💡", "🔥", "📚", "✨"]):
                return f"📚 {original_title}"
        
        return original_title or "💡 每日精选"
    
    def _format_body(self, content: str) -> str:
        """格式化正文"""
        # 限制长度
        if len(content) > self.max_length:
            content = content[:self.max_length] + "..."
        
        # 添加段落间距
        paragraphs = content.split('\n')
        formatted = '\n\n'.join(p.strip() for p in paragraphs if p.strip())
        
        # 添加小红书风格的开头和结尾
        opening = "姐妹们，今天分享一个超有用的观点👇\n\n"
        closing = "\n\n💭 你怎么看？评论区聊聊~"
        
        return opening + formatted + closing
    
    def _generate_tags(self, item: ContentItem, content: str) -> List[str]:
        """生成标签"""
        tags = []
        
        # 根据内容选择相关标签
        content_lower = content.lower()
        
        # 科技/AI 相关内容
        if any(kw in content_lower for kw in ["ai", "人工智能", "技术", "python", "code"]):
            tags.extend(["#AI", "#科技", "#编程"])
        
        # 职场/成长内容
        if any(kw in content_lower for kw in ["work", "startup", "创业", "职场", "效率"]):
            tags.extend(["#职场干货", "#创业", "#效率工具"])
        
        # 学习/知识内容
        if any(kw in content_lower for kw in ["learn", "read", "book", "学习", "读书"]):
            tags.extend(["#学习方法", "#读书", "#知识分享"])
        
        # 添加默认标签
        if len(tags) < 3:
            tags.extend(self.DEFAULT_TAGS[:3-len(tags)])
        
        # 限制标签数量
        return tags[:5]
    
    def _assemble_post(
        self,
        title: str,
        body: str,
        tags: List[str],
        source_url: str = None,
    ) -> str:
        """组装完整帖子"""
        lines = [
            title,
            "",
            body,
            "",
            " ".join(tags),
        ]
        
        if source_url:
            lines.extend(["", f"🔗 原文: {source_url}"])
        
        return "\n".join(lines)
    
    def to_post_object(self, item: ContentItem) -> XiaoHongShuPost:
        """转换为小红书发布对象"""
        return XiaoHongShuPost(
            title=item.title,
            content=item.xiaohongshu_content or "",
            tags=item.xiaohongshu_tags,
            original_url=item.url,
        )
