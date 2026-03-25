"""记忆自动提取系统

从对话中提取关键信息，更新用户记忆档案
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import re
import json

from .llm import LLMManager, Message
from ..memory.storage.user_isolated import UserMemoryManager
from ..memory.storage.markdown_store import MarkdownMemoryStore


@dataclass
class ExtractedInsight:
    """提取的洞察"""
    category: str  # identity / skill / project / goal / preference / note
    content: str
    confidence: float  # 0-1
    source: str  # 对话原文
    timestamp: datetime


@dataclass
class MemoryUpdate:
    """记忆更新建议"""
    file_path: Path
    update_type: str  # add / modify / new_section
    section: Optional[str]
    content: str
    reason: str


class MemoryExtractor:
    """记忆提取器
    
    自动从对话中提取有价值的信息
    """
    
    # 提取提示词
    EXTRACTION_PROMPT = """你是一个专业的记忆提取助手。请分析以下对话，提取有价值的信息来更新用户的记忆档案。

请从以下维度分析：
1. **身份 (identity)**: 用户的基本信息、价值观、性格特点的变化
2. **技能 (skill)**: 新学习的技能、技能水平的变化
3. **项目 (project)**: 新项目、项目进展、里程碑
4. **目标 (goal)**: 新目标、目标调整
5. **偏好 (preference)**: 喜好、习惯、偏好的变化
6. **重要信息 (note)**: 其他值得记录的重要信息

对于每个提取的信息：
- 给出具体内容
- 评估置信度 (0-1)
- 说明为什么重要

只提取明确提到或强烈暗示的信息，不要猜测。

对话：
{conversation}

请以 JSON 格式返回：
{{
    "insights": [
        {{
            "category": "identity/skill/project/goal/preference/note",
            "content": "提取的信息",
            "confidence": 0.9,
            "reason": "为什么重要"
        }}
    ]
}}"""
    
    def __init__(
        self,
        llm_manager: LLMManager,
        memory_manager: UserMemoryManager
    ):
        self.llm_manager = llm_manager
        self.memory_manager = memory_manager
    
    def extract_from_conversation(
        self,
        user_message: str,
        assistant_response: str
    ) -> List[ExtractedInsight]:
        """从单轮对话中提取洞察
        
        Args:
            user_message: 用户消息
            assistant_response: 助手回复
            
        Returns:
            List[ExtractedInsight]: 提取的洞察列表
        """
        conversation = f"用户: {user_message}\n\n助手: {assistant_response}"
        
        # 构建提示词
        prompt = self.EXTRACTION_PROMPT.format(conversation=conversation)
        
        try:
            # 调用 LLM 提取
            response = self.llm_manager.quick_chat(
                prompt=prompt,
                system="你是一个专业的记忆提取助手，只返回 JSON 格式结果。"
            )
            
            # 解析 JSON
            insights = self._parse_extraction_response(response)
            
            # 添加时间戳和来源
            for insight in insights:
                insight.timestamp = datetime.now()
                insight.source = user_message[:200]  # 前200字符
            
            return insights
            
        except Exception as e:
            print(f"记忆提取失败: {e}")
            return []
    
    def _parse_extraction_response(self, response: str) -> List[ExtractedInsight]:
        """解析 LLM 的提取响应"""
        insights = []
        
        try:
            # 提取 JSON 部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                for item in data.get("insights", []):
                    insight = ExtractedInsight(
                        category=item.get("category", "note"),
                        content=item.get("content", ""),
                        confidence=item.get("confidence", 0.5),
                        reason=item.get("reason", ""),
                        source="",
                        timestamp=datetime.now()
                    )
                    
                    # 只保留置信度较高的洞察
                    if insight.confidence >= 0.7:
                        insights.append(insight)
        
        except json.JSONDecodeError:
            # 如果不是有效 JSON，尝试简单解析
            pass
        
        return insights
    
    def generate_memory_updates(
        self,
        insights: List[ExtractedInsight]
    ) -> List[MemoryUpdate]:
        """根据洞察生成记忆更新建议
        
        Args:
            insights: 提取的洞察列表
            
        Returns:
            List[MemoryUpdate]: 更新建议列表
        """
        updates = []
        
        for insight in insights:
            update = self._create_update_for_insight(insight)
            if update:
                updates.append(update)
        
        return updates
    
    def _create_update_for_insight(self, insight: ExtractedInsight) -> Optional[MemoryUpdate]:
        """为单个洞察创建更新建议"""
        
        if insight.category == "identity":
            return MemoryUpdate(
                file_path=self.memory_manager.user_memory_dir / "identity" / "profile.md",
                update_type="modify",
                section="基本信息",
                content=insight.content,
                reason=insight.reason
            )
        
        elif insight.category == "skill":
            return MemoryUpdate(
                file_path=self.memory_manager.user_memory_dir / "skills" / "learning_map.md",
                update_type="modify",
                section="当前正在学习",
                content=insight.content,
                reason=insight.reason
            )
        
        elif insight.category == "project":
            return MemoryUpdate(
                file_path=self.memory_manager.user_memory_dir / "projects" / "active.md",
                update_type="add",
                section=None,
                content=insight.content,
                reason=insight.reason
            )
        
        elif insight.category == "goal":
            return MemoryUpdate(
                file_path=self.memory_manager.user_memory_dir / "identity" / "goals.md",
                update_type="add",
                section=None,
                content=insight.content,
                reason=insight.reason
            )
        
        elif insight.category in ["preference", "note"]:
            # 保存到 insights 文件
            return MemoryUpdate(
                file_path=self.memory_manager.user_memory_dir / "patterns" / "insights.md",
                update_type="add",
                section=None,
                content=f"- {insight.content}\n  （{insight.reason}）",
                reason=insight.reason
            )
        
        return None
    
    def apply_update(self, update: MemoryUpdate, confirm: bool = False) -> bool:
        """应用记忆更新
        
        Args:
            update: 更新建议
            confirm: 是否需要确认
            
        Returns:
            bool: 是否成功
        """
        if confirm:
            # TODO: 交互式确认
            pass
        
        try:
            if update.update_type == "new_section":
                # 创建新章节
                self._add_section(update.file_path, update.section, update.content)
            
            elif update.update_type == "modify":
                # 修改现有章节
                self._modify_section(update.file_path, update.section, update.content)
            
            elif update.update_type == "add":
                # 添加内容
                self._append_content(update.file_path, update.content)
            
            return True
            
        except Exception as e:
            print(f"应用更新失败: {e}")
            return False
    
    def _add_section(self, filepath: Path, section_title: str, content: str):
        """添加新章节"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        section_content = f"\n## {section_title}\n\n{content}\n"
        
        if filepath.exists():
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(section_content)
        else:
            # 创建新文件
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"---\ntype: note\ncreated_at: {datetime.now().isoformat()}\n---\n\n")
                f.write(section_content)
    
    def _modify_section(self, filepath: Path, section_title: str, new_content: str):
        """修改现有章节"""
        if not filepath.exists():
            return self._add_section(filepath, section_title, new_content)
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 查找章节
        pattern = rf"(## {re.escape(section_title)}\n\n)(.*?)(?=\n## |\Z)"
        
        if re.search(pattern, content, re.DOTALL):
            # 更新现有章节
            updated = re.sub(
                pattern,
                rf"\1{new_content}\n",
                content,
                flags=re.DOTALL
            )
        else:
            # 章节不存在，添加
            updated = content + f"\n## {section_title}\n\n{new_content}\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated)
    
    def _append_content(self, filepath: Path, content: str):
        """追加内容到文件"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n- [{timestamp}] {content}\n"
        
        if filepath.exists():
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(entry)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"---\ntype: note\ncreated_at: {datetime.now().isoformat()}\n---\n\n")
                f.write(f"# 洞察记录\n")
                f.write(entry)


class SimpleMemoryExtractor:
    """简单的记忆提取器（不依赖 LLM）
    
    使用规则提取关键信息
    """
    
    # 关键词模式
    PATTERNS = {
        "skill": [
            r"(?:在学|学习|练习|掌握)\s*([\u4e00-\u9fa5]+)",
            r"([\u4e00-\u9fa5]+)\s*(?:技能|技术|语言)",
        ],
        "goal": [
            r"(?:目标|计划|想|希望)\s*.*?(?:学会|完成|达到|成为)",
        ],
        "preference": [
            r"(?:喜欢|偏好|习惯|讨厌)\s*([\u4e00-\u9fa5]+)",
        ],
    }
    
    def extract(self, text: str) -> List[Dict[str, Any]]:
        """简单提取"""
        insights = []
        
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    insights.append({
                        "category": category,
                        "content": match if isinstance(match, str) else match[0],
                        "confidence": 0.6,
                    })
        
        return insights
