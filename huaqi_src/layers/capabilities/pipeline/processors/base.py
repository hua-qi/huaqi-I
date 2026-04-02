"""处理器基类"""

from abc import ABC, abstractmethod
from typing import List

from ..models import ContentItem, PipelineResult


class BaseProcessor(ABC):
    """内容处理器基类"""
    
    name: str = "base"
    
    @abstractmethod
    async def process(self, item: ContentItem) -> PipelineResult:
        """处理内容
        
        Args:
            item: 内容条目
            
        Returns:
            处理结果
        """
        pass
    
    async def process_batch(self, items: List[ContentItem]) -> List[PipelineResult]:
        """批量处理"""
        results = []
        for item in items:
            try:
                result = await self.process(item)
                results.append(result)
            except Exception as e:
                results.append(PipelineResult(
                    item=item,
                    success=False,
                    stage=self.name,
                    error=str(e),
                ))
        return results
