"""内容翻译处理器"""

import os
from typing import Optional

from ..models import ContentItem, ContentStatus, PipelineResult
from .base import BaseProcessor


class Translator(BaseProcessor):
    """将英文内容翻译为中文"""
    
    name = "translator"
    
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
    
    async def process(self, item: ContentItem) -> PipelineResult:
        """翻译内容"""
        try:
            content = item.summary or item.content
            
            # 检测是否为英文内容
            if not self._is_english(content):
                # 已经是中文，跳过
                item.translated_content = content
                item.status = ContentStatus.TRANSLATED
                return PipelineResult(item=item, success=True, stage=self.name)
            
            # 翻译
            if self.use_llm:
                translated = await self._translate_with_llm(content)
            else:
                translated = self._simple_translate(content)
            
            item.translated_content = translated
            item.status = ContentStatus.TRANSLATED
            
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
    
    def _is_english(self, text: str) -> bool:
        """检测文本主要为英文"""
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        return ascii_chars / len(text) > 0.7 if text else False
    
    async def _translate_with_llm(self, text: str) -> str:
        """使用 LLM 翻译"""
        # TODO: 集成真实 LLM 翻译
        # 当前返回模拟翻译结果
        return self._simple_translate(text)
    
    def _simple_translate(self, text: str) -> str:
        """简单翻译 (模拟)"""
        # 实际项目中应调用翻译 API 或 LLM
        # 这里返回带标记的原文表示已"翻译"
        return f"[中文翻译] {text[:200]}..."
