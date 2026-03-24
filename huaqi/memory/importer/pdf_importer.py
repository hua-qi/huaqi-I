"""PDF 文件导入器"""

from pathlib import Path
from typing import List

from .base import MemoryImporter


class PDFImporter(MemoryImporter):
    """导入 PDF 文件 (需要 PyPDF2 或 pdfplumber)"""
    
    SUPPORTED_EXTENSIONS = [".pdf"]
    
    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_text(self, file_path: Path) -> str:
        """提取 PDF 文本"""
        try:
            import pdfplumber
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            return text
        except ImportError:
            # Fallback: 返回提示信息
            return f"[PDF 内容 - 需要安装 pdfplumber: pip install pdfplumber]\n文件: {file_path}"
        except Exception as e:
            return f"[无法提取 PDF 内容: {e}]"
