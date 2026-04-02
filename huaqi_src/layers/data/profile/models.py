"""用户画像数据模型

定义所有用户画像相关的数据结构：
- UserIdentity：身份信息
- UserPreferences：偏好设置
- UserBackground：背景信息
- UserProfile：完整画像
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class UserIdentity:
    """用户身份信息"""
    name: Optional[str] = None
    nickname: Optional[str] = None
    birth_date: Optional[str] = None
    location: Optional[str] = None
    occupation: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserIdentity":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_empty(self) -> bool:
        return all(v is None for v in [self.name, self.nickname, self.birth_date,
                                       self.location, self.occupation, self.company])


@dataclass
class UserPreferences:
    """用户偏好"""
    communication_style: Optional[str] = None
    response_length: Optional[str] = None
    topics_of_interest: List[str] = field(default_factory=list)
    disliked_topics: List[str] = field(default_factory=list)
    preferred_languages: List[str] = field(default_factory=lambda: ["zh"])

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPreferences":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class UserBackground:
    """用户背景信息"""
    education: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    hobbies: List[str] = field(default_factory=list)
    family_info: Optional[str] = None
    life_goals: List[str] = field(default_factory=list)
    values: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserBackground":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class UserProfile:
    """完整用户画像"""
    identity: UserIdentity = field(default_factory=UserIdentity)
    preferences: UserPreferences = field(default_factory=UserPreferences)
    background: UserBackground = field(default_factory=UserBackground)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 1
    extraction_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "preferences": self.preferences.to_dict(),
            "background": self.background.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "extraction_history": self.extraction_history[-20:],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        return cls(
            identity=UserIdentity.from_dict(data.get("identity", {})),
            preferences=UserPreferences.from_dict(data.get("preferences", {})),
            background=UserBackground.from_dict(data.get("background", {})),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            version=data.get("version", 1),
            extraction_history=data.get("extraction_history", []),
        )

    def get_summary(self) -> str:
        """生成画像摘要（用于 Prompt）"""
        parts = []

        identity_parts = []
        if self.identity.name:
            identity_parts.append(f"名字是{self.identity.name}")
        if self.identity.nickname:
            identity_parts.append(f"昵称{self.identity.nickname}")
        if self.identity.occupation:
            identity_parts.append(f"职业是{self.identity.occupation}")
        if self.identity.location:
            identity_parts.append(f"住在{self.identity.location}")

        if identity_parts:
            parts.append("用户" + "，".join(identity_parts) + "。")

        if self.background.skills:
            parts.append(f"用户技能：{', '.join(self.background.skills)}。")
        if self.background.hobbies:
            parts.append(f"用户爱好：{', '.join(self.background.hobbies)}。")
        if self.background.life_goals:
            parts.append(f"用户目标：{', '.join(self.background.life_goals)}。")

        return "\n".join(parts) if parts else ""

    def add_extraction(self, extracted_fields: Dict[str, Any], source_message: str):
        """记录一次提取"""
        self.extraction_history.append({
            "timestamp": datetime.now().isoformat(),
            "fields": extracted_fields,
            "source_preview": source_message[:100] + "..." if len(source_message) > 100 else source_message,
        })
        self.updated_at = datetime.now().isoformat()
        self.version += 1
