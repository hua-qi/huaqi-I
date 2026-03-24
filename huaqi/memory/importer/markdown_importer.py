"""Markdown 文件导入器"""

from pathlib import Path
from typing import List
import re

from .base import MemoryImporter


class MarkdownImporter(MemoryImporter):
    """导入 Markdown 文件"""
    
    SUPPORTED_EXTENSIONS = [".md", ".markdown", ".mdx"]
    
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_text(self, file_path: Path) -> str:
        """提取 Markdown 文本"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    
    def _extract_insights(self, content: str) -> List[str]:
        """从 Markdown 中提取关键信息"""
        insights = []
        
        # 提取标题
        headers = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
        if headers:
            insights.append(f"主要主题: {', '.join(headers[:3])}")
        
        # 提取加粗内容
        bold_texts = re.findall(r'\*\*(.+?)\*\*', content)
        if bold_texts:
            insights.append(f"关键概念: {', '.join(set(bold_texts[:5]))}")
        
        # 提取列表项
        list_items = re.findall(r'^[-*]\s+(.+)$', content, re.MULTILINE)
        if list_items:
            insights.append(f"包含 {len(list_items)} 个要点")
        
        return insights
