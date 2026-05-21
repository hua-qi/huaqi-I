"""跨层共享的基础数据模型。所有层都可以依赖此模块。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class MessageRole(Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    reasoning_content: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.reasoning_content is not None:
            result["reasoning_content"] = self.reasoning_content
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        role = MessageRole(data.get("role", "user"))
        content = data.get("content", "")
        reasoning_content = data.get("reasoning_content")
        return cls(
            role=role,
            content=content,
            reasoning_content=reasoning_content,
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        return cls(role=MessageRole.ASSISTANT, content=content)
