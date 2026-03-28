"""用户画像管理器

负责用户画像的持久化存储、加载和字段更新。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from huaqi_src.core.config_paths import get_memory_dir
from huaqi_src.core.profile_models import UserIdentity, UserPreferences, UserBackground, UserProfile


class UserProfileManager:
    """用户画像管理器"""

    PROFILE_FILENAME = "user_profile.yaml"

    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or get_memory_dir()
        self.profile_path = self.memory_dir / self.PROFILE_FILENAME
        self._profile: Optional[UserProfile] = None

    def _load_or_create(self) -> UserProfile:
        if self.profile_path.exists():
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return UserProfile.from_dict(data)
        return UserProfile()

    @property
    def profile(self) -> UserProfile:
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
        """从用户消息中提取用户信息"""
        if llm_manager is not None:
            return self._extract_with_llm(user_message, llm_manager)
        return {}

    def _extract_with_llm(self, user_message: str, llm_manager) -> Dict[str, Any]:
        """使用 LLM 智能提取用户信息"""
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

            if "```" in content:
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
            extracted = {k: v for k, v in extracted.items() if v and v not in ([], "", None, "null")}

            list_fields = ['skills', 'hobbies', 'life_goals', 'values']
            for f in list_fields:
                if f in extracted and isinstance(extracted[f], str):
                    extracted[f] = [extracted[f]]

            if extracted:
                self._apply_extraction(extracted, user_message)

            return extracted

        except Exception:
            return {}

    def _apply_extraction(self, extracted: Dict[str, Any], source_message: str):
        """应用提取结果到画像"""
        identity_fields = ['name', 'nickname', 'birth_date', 'location', 'occupation', 'company']
        for f in identity_fields:
            if f in extracted and extracted[f]:
                setattr(self.profile.identity, f, extracted[f])

        if 'skills' in extracted:
            for skill in extracted['skills']:
                if skill not in self.profile.background.skills:
                    self.profile.background.skills.append(skill)

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

        current_summary = self.profile.get_summary() or "暂无"
        prompt = self.get_llm_extraction_prompt().format(current_profile=current_summary)

        messages = [
            Message.system(prompt),
            Message.user(f"用户消息：{user_message}")
        ]

        try:
            response = llm_manager.chat(messages)
            content = response.content.strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            extracted = json.loads(content.strip())
            extracted = {k: v for k, v in extracted.items() if v}

            if extracted:
                self._apply_extraction(extracted, user_message)

            return extracted

        except Exception:
            return self.extract_from_message(user_message)


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
