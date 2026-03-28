"""用户画像模块

存储和管理用户个人信息，从对话中自动提取和更新
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import yaml
import json
import re

from huaqi_src.core.config_paths import get_data_dir, get_memory_dir


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
    communication_style: Optional[str] = None  # formal, casual, professional
    response_length: Optional[str] = None      # short, medium, long
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
    # 身份信息
    identity: UserIdentity = field(default_factory=UserIdentity)
    
    # 偏好设置
    preferences: UserPreferences = field(default_factory=UserPreferences)
    
    # 背景信息
    background: UserBackground = field(default_factory=UserBackground)
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 1
    
    # 提取历史记录
    extraction_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "preferences": self.preferences.to_dict(),
            "background": self.background.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "extraction_history": self.extraction_history[-20:],  # 只保留最近20条
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
        
        # 身份信息
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
        
        # 背景信息
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


class UserProfileManager:
    """用户画像管理器"""
    
    PROFILE_FILENAME = "user_profile.yaml"
    
    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or get_memory_dir()
        self.profile_path = self.memory_dir / self.PROFILE_FILENAME
        self._profile: Optional[UserProfile] = None
    
    def _load_or_create(self) -> UserProfile:
        """加载或创建用户画像"""
        if self.profile_path.exists():
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return UserProfile.from_dict(data)
        return UserProfile()
    
    @property
    def profile(self) -> UserProfile:
        """获取用户画像（懒加载）"""
        if self._profile is None:
            self._profile = self._load_or_create()
        return self._profile
    
    def save(self):
        """保存用户画像"""
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            yaml.dump(self.profile.to_dict(), f, allow_unicode=True, sort_keys=False)
    
    def update_identity(self, **kwargs):
        """更新身份信息"""
        for key, value in kwargs.items():
            if hasattr(self.profile.identity, key) and value:
                setattr(self.profile.identity, key, value)
        self.profile.updated_at = datetime.now().isoformat()
        self.save()
    
    def update_preferences(self, **kwargs):
        """更新偏好设置"""
        for key, value in kwargs.items():
            if hasattr(self.profile.preferences, key) and value:
                setattr(self.profile.preferences, key, value)
        self.profile.updated_at = datetime.now().isoformat()
        self.save()
    
    def update_background(self, **kwargs):
        """更新背景信息"""
        for key, value in kwargs.items():
            if hasattr(self.profile.background, key) and value:
                setattr(self.profile.background, key, value)
        self.profile.updated_at = datetime.now().isoformat()
        self.save()
    
    def get_system_prompt_addition(self) -> str:
        """获取用于系统提示词的画像信息"""
        summary = self.profile.get_summary()
        if not summary:
            return ""
        return f"\n\n### 用户信息\n{summary}"
    
    def extract_from_message(self, user_message: str, llm_manager=None) -> Dict[str, Any]:
        """从用户消息中提取用户信息
        
        优先使用 LLM 智能提取，如果不可用则返回空
        """
        # 如果提供了 LLM 管理器，使用 LLM 提取
        if llm_manager is not None:
            return self._extract_with_llm(user_message, llm_manager)
        
        # 没有 LLM 时不提取（避免误提取）
        return {}
    
    def _extract_with_llm(self, user_message: str, llm_manager) -> Dict[str, Any]:
        """使用 LLM 智能提取用户信息"""
        # 构建提示词
        current_summary = self.profile.get_summary() or "暂无已知信息"
        
        prompt = f"""从用户消息中提取用户的个人信息。

规则：
1. 只提取明确提到的信息，不要猜测
2. 如果用户说"我是子蒙"，提取 name="子蒙"
3. 如果用户说"我是一名工程师"，提取 occupation="工程师"
4. 如果用户说"我住在北京"，提取 location="北京"
5. 如果用户说"我会Python"，提取 skills=["Python"]
6. 如果用户说"我喜欢阅读"，提取 hobbies=["阅读"]
7. 如果没有新信息，返回空对象 {{}}

当前已知信息：
{current_summary}

用户消息：
{user_message}

请提取信息，以 JSON 格式返回：
{{
    "name": "名字",
    "nickname": "昵称",
    "occupation": "职业",
    "location": "所在地",
    "company": "公司",
    "skills": ["技能1", "技能2"],
    "hobbies": ["爱好1", "爱好2"],
    "life_goals": ["目标1"]
}}

只返回 JSON，不要其他内容。"""

        try:
            from huaqi_src.core.llm import Message
            
            messages = [
                Message.system("你是一个信息提取助手，从用户消息中提取结构化信息。"),
                Message.user(prompt)
            ]
            
            response = llm_manager.chat(messages)
            content = response.content.strip()
            
            # 清理 markdown 代码块
            if "```" in content:
                # 提取 ```json 或 ``` 中的内容
                lines = content.split("\n")
                json_lines = []
                in_json = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_json = not in_json
                        continue
                    if in_json:
                        json_lines.append(line)
                if json_lines:
                    content = "\n".join(json_lines)
            
            extracted = json.loads(content.strip())
            
            # 过滤空值和无效值
            extracted = {k: v for k, v in extracted.items() if v and v not in ([], "", None, "null")}
            
            # 确保列表字段是列表
            list_fields = ['skills', 'hobbies', 'life_goals', 'values']
            for field in list_fields:
                if field in extracted and isinstance(extracted[field], str):
                    extracted[field] = [extracted[field]]
            
            if extracted:
                self._apply_extraction(extracted, user_message)
            
            return extracted
            
        except Exception as e:
            # LLM 提取失败，静默返回空
            return {}
    
    def _apply_extraction(self, extracted: Dict[str, Any], source_message: str):
        """应用提取结果到画像"""
        # 身份信息
        identity_fields = ['name', 'nickname', 'birth_date', 'location', 'occupation', 'company']
        for field in identity_fields:
            if field in extracted and extracted[field]:
                setattr(self.profile.identity, field, extracted[field])
        
        # 背景信息（列表类型需要追加）
        if 'skills' in extracted:
            for skill in extracted['skills']:
                if skill not in self.profile.background.skills:
                    self.profile.background.skills.append(skill)
        
        # 记录提取历史
        self.profile.add_extraction(extracted, source_message)
        self.save()
    
    def get_llm_extraction_prompt(self) -> str:
        """获取用于 LLM 提取用户信息的提示词"""
        return """从用户的消息中提取个人信息。只提取明确提到的信息，不要猜测。

当前已知信息：
{current_profile}

请从以下消息中提取新的信息（JSON格式）：
{{
    "name": "名字（如果有）",
    "nickname": "昵称（如果有）",
    "occupation": "职业（如果有）",
    "location": "所在地（如果有）",
    "skills": ["技能1", "技能2"],
    "hobbies": ["爱好1", "爱好2"],
    "life_goals": ["目标1", "目标2"]
}}

只返回JSON，如果没有新信息返回空对象 {{}}。"""
    
    def extract_with_llm(self, user_message: str, llm_manager) -> Dict[str, Any]:
        """使用 LLM 提取用户信息"""
        from huaqi_src.core.llm import Message
        
        # 构建提示词
        current_summary = self.profile.get_summary() or "暂无"
        prompt = self.get_llm_extraction_prompt().format(current_profile=current_summary)
        
        messages = [
            Message.system(prompt),
            Message.user(f"用户消息：{user_message}")
        ]
        
        try:
            response = llm_manager.chat(messages)
            content = response.content.strip()
            
            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            extracted = json.loads(content.strip())
            
            # 过滤空值
            extracted = {k: v for k, v in extracted.items() if v}
            
            if extracted:
                self._apply_extraction(extracted, user_message)
            
            return extracted
            
        except Exception as e:
            # 如果 LLM 提取失败，回退到规则提取
            return self.extract_from_message(user_message)


# 全局管理器实例
_profile_manager: Optional[UserProfileManager] = None


def get_profile_manager() -> UserProfileManager:
    """获取全局用户画像管理器"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = UserProfileManager()
    return _profile_manager


def init_profile_manager(memory_dir: Optional[Path] = None) -> UserProfileManager:
    """初始化全局用户画像管理器"""
    global _profile_manager
    _profile_manager = UserProfileManager(memory_dir)
    return _profile_manager
