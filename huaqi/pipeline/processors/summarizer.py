"""内容摘要处理器"""

from ..models import ContentItem, ContentStatus, PipelineResult
from .base import BaseProcessor


class Summarizer(BaseProcessor):
    """生成内容摘要"""
    
    name = "summarizer"
    
    def __init__(self, max_length: int = 500):
        self.max_length = max_length
    
    async def process(self, item: ContentItem) -> PipelineResult:
        """生成摘要"""
        try:
            # 简单提取前几句作为摘要
            # 实际应使用 LLM 生成高质量摘要
            content = item.content
            
            # 如果内容短，直接使用
            if len(content) <= self.max_length:
                item.summary = content
            else:
                # 截取前 max_length 字符，在句号处截断
                truncated = content[:self.max_length]
                last_period = truncated.rfind('.')
                last_cn_period = truncated.rfind('。')
                cut_pos = max(last_period, last_cn_period)
                
                if cut_pos > self.max_length * 0.5:
                    item.summary = truncated[:cut_pos + 1]
                else:
                    item.summary = truncated + "..."
            
            item.status = ContentStatus.SUMMARIZED
            
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
