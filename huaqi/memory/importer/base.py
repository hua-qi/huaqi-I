"""导入器基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class ImportResult:
    """导入结果"""
    success: bool
    file_path: Path
    memory_type: str  # identity / project / skill / insight / note
    title: str
    content: str
    metadata: Dict[str, Any]
    tags: List[str]
    error_message: Optional[str] = None
    extracted_insights: List[str] = None
    
    def __post_init__(self):
        if self.extracted_insights is None:
            self.extracted_insights = []


class MemoryImporter(ABC):
    """记忆导入器基类"""
    
    SUPPORTED_EXTENSIONS: List[str] = []
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """检查是否能处理该文件"""
        pass
    
    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """提取文本内容"""
        pass
    
    def import_file(self, file_path: Path, auto_classify: bool = True) -> ImportResult:
        """导入文件为记忆
        
        Args:
            file_path: 文件路径
            auto_classify: 是否自动分类
            
        Returns:
            ImportResult: 导入结果
        """
        try:
            # 1. 提取文本
            content = self.extract_text(file_path)
            
            if not content.strip():
                return ImportResult(
                    success=False,
                    file_path=file_path,
                    memory_type="unknown",
                    title=file_path.stem,
                    content="",
                    metadata={},
                    tags=[],
                    error_message="文件内容为空"
                )
            
            # 2. 自动分类 (如果启用)
            if auto_classify and self.llm_client:
                classification = self._classify_content(content, file_path)
            else:
                classification = self._default_classification(file_path)
            
            # 3. 提取关键信息
            if self.llm_client:
                insights = self._extract_insights(content)
                metadata = self._enrich_metadata(content, classification)
            else:
                insights = []
                metadata = self._basic_metadata(file_path)
            
            return ImportResult(
                success=True,
                file_path=file_path,
                memory_type=classification["type"],
                title=classification.get("title", file_path.stem),
                content=content,
                metadata=metadata,
                tags=classification.get("tags", []),
                extracted_insights=insights
            )
            
        except Exception as e:
            return ImportResult(
                success=False,
                file_path=file_path,
                memory_type="unknown",
                title=file_path.stem,
                content="",
                metadata={},
                tags=[],
                error_message=str(e)
            )
    
    def _classify_content(self, content: str, file_path: Path) -> Dict[str, Any]:
        """使用 LLM 自动分类内容"""
        prompt = f"""分析以下文档内容，判断它属于哪种类型：

文档路径: {file_path}
内容前 1000 字:
{content[:1000]}...

请返回 JSON 格式:
{{
    "type": "identity|project|skill|insight|note",
    "title": "文档标题",
    "tags": ["标签1", "标签2"],
    "summary": "一句话摘要",
    "importance": 0.8  // 0-1 重要程度
}}
"""
        try:
            # TODO: 调用 LLM 进行分类
            # 这里先返回默认分类
            return self._default_classification(file_path)
        except:
            return self._default_classification(file_path)
    
    def _default_classification(self, file_path: Path) -> Dict[str, Any]:
        """默认分类规则"""
        path_lower = str(file_path).lower()
        name_lower = file_path.stem.lower()
        
        # 根据路径关键词分类
        if any(kw in path_lower for kw in ["intro", "about", "me", "profile", "个人"]):
            return {
                "type": "identity",
                "title": file_path.stem,
                "tags": ["identity"],
                "importance": 0.9
            }
        elif any(kw in path_lower for kw in ["project", "项目", "工作", "work"]):
            return {
                "type": "project",
                "title": file_path.stem,
                "tags": ["project"],
                "importance": 0.8
            }
        elif any(kw in path_lower for kw in ["learn", "skill", "学习", "技能", "guitar", "英语"]):
            return {
                "type": "skill",
                "title": file_path.stem,
                "tags": ["skill"],
                "importance": 0.7
            }
        else:
            return {
                "type": "note",
                "title": file_path.stem,
                "tags": ["note"],
                "importance": 0.5
            }
    
    def _extract_insights(self, content: str) -> List[str]:
        """提取关键洞察"""
        # TODO: 使用 LLM 提取关键信息
        return []
    
    def _enrich_metadata(self, content: str, classification: Dict) -> Dict[str, Any]:
        """丰富元数据"""
        return {
            "importance": classification.get("importance", 0.5),
            "summary": classification.get("summary", ""),
            "word_count": len(content),
            "imported_at": datetime.now().isoformat(),
        }
    
    def _basic_metadata(self, file_path: Path) -> Dict[str, Any]:
        """基础元数据"""
        stat = file_path.stat()
        return {
            "imported_at": datetime.now().isoformat(),
            "original_path": str(file_path),
            "file_size": stat.st_size,
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
