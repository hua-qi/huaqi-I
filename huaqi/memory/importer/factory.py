"""导入器工厂"""

from pathlib import Path
from typing import List, Type, Optional

from .base import MemoryImporter
from .markdown_importer import MarkdownImporter
from .pdf_importer import PDFImporter
from .docx_importer import DocxImporter


class ImporterFactory:
    """导入器工厂"""
    
    _importers: List[Type[MemoryImporter]] = [
        MarkdownImporter,
        PDFImporter,
        DocxImporter,
        # TODO: 添加更多导入器
        # TextImporter,
        # JSONImporter,
        # ExcelImporter,
    ]
    
    @classmethod
    def get_importer(cls, file_path: Path, llm_client=None) -> Optional[MemoryImporter]:
        """获取适合处理该文件的导入器"""
        for importer_class in cls._importers:
            importer = importer_class(llm_client)
            if importer.can_handle(file_path):
                return importer
        return None
    
    @classmethod
    def list_supported_formats(cls) -> List[str]:
        """列出支持的格式"""
        formats = []
        for importer_class in cls._importers:
            formats.extend(importer_class.SUPPORTED_EXTENSIONS)
        return formats
