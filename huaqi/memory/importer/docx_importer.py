"""Word 文档导入器"""

from pathlib import Path
from typing import List

from .base import MemoryImporter


class DocxImporter(MemoryImporter):
    """导入 Word 文档 (需要 python-docx)"""
    
    SUPPORTED_EXTENSIONS = [".docx", ".doc"]
    
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_text(self, file_path: Path) -> str:
        """提取 Word 文本"""
        try:
            import docx
            doc = docx.Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except ImportError:
            return f"[Word 文档内容 - 需要安装 python-docx: pip install python-docx]\n文件: {file_path}"
        except Exception as e:
            return f"[无法提取 Word 内容: {e}]"
