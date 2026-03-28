"""用户画像模块

存储和管理用户个人信息，从对话中自动提取和更新
支持从日记、对话历史等多数据源综合分析提取
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
import yaml
import json
import re
import threading

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


class UserDataExtractor:
    """启动时从多数据源提取用户信息
    
    不再每次对话都调用 LLM，而是在 CLI 启动时统一分析：
    - 用户画像 (profile)
    - 日记 (diary) 
    - 对话历史 (conversations)
    
    异步执行，不阻塞用户输入。
    失败时自动重试，直到成功。
    """
    
    # 重试配置
    MAX_RETRIES = 3           # 最大重试次数
    RETRY_DELAY_BASE = 2.0    # 基础延迟（秒），指数退避
    LLM_TIMEOUT = 30          # 每次 LLM 调用超时（秒）
    
    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or get_memory_dir()
        self._extraction_result: Optional[Dict[str, Any]] = None
        self._extraction_thread: Optional[threading.Thread] = None
        self._is_extracting = False
        self._retry_count = 0
        self._last_error: Optional[str] = None
        self._on_status_update: Optional[Callable[[str], None]] = None  # 状态更新回调
        
    def _notify_status(self, message: str):
        """通知状态更新"""
        if self._on_status_update:
            try:
                self._on_status_update(message)
            except Exception:
                pass
        
    def _collect_user_data(self) -> Dict[str, Any]:
        """收集所有用户相关数据"""
        data = {
            "profile": {},
            "recent_diaries": [],
            "recent_conversations": [],
            "last_extraction": None
        }
        
        # 1. 收集用户画像
        try:
            profile_manager = get_profile_manager()
            profile = profile_manager.profile
            data["profile"] = {
                "identity": profile.identity.to_dict(),
                "preferences": profile.preferences.to_dict(),
                "background": profile.background.to_dict(),
                "extraction_history_count": len(profile.extraction_history)
            }
            # 获取上次提取时间
            if profile.extraction_history:
                data["last_extraction"] = profile.extraction_history[-1].get("timestamp")
        except Exception:
            pass
        
        # 2. 收集最近日记
        try:
            from huaqi_src.core.diary_simple import DiaryStore
            diary_store = DiaryStore(self.memory_dir)
            recent_diaries = diary_store.list_entries(limit=5)
            data["recent_diaries"] = [
                {
                    "date": d.date,
                    "content_preview": d.content[:200] + "..." if len(d.content) > 200 else d.content,
                    "mood": d.mood,
                    "tags": d.tags
                }
                for d in recent_diaries
            ]
        except Exception:
            pass
        
        # 3. 收集最近对话
        try:
            from huaqi_src.memory.storage.markdown_store import MarkdownMemoryStore
            conv_store = MarkdownMemoryStore(self.memory_dir / "conversations")
            conversations = conv_store.list_conversations(limit=3)
            data["recent_conversations"] = [
                {
                    "session_id": c.get("session_id", ""),
                    "created_at": c.get("created_at", ""),
                    "turns": c.get("turns", 0)
                }
                for c in conversations[:3]
            ]
        except Exception:
            pass
            
        return data
    
    def _build_extraction_prompt(self, user_data: Dict[str, Any]) -> str:
        """构建提取提示词"""
        profile_info = user_data.get("profile", {})
        diaries = user_data.get("recent_diaries", [])
        conversations = user_data.get("recent_conversations", [])
        last_extraction = user_data.get("last_extraction")
        
        # 构建日记内容摘要
        diary_text = ""
        if diaries:
            diary_lines = []
            for d in diaries[:3]:  # 最多3篇日记
                diary_lines.append(f"【{d['date']}】")
                if d.get("mood"):
                    diary_lines.append(f"情绪: {d['mood']}")
                if d.get("tags"):
                    diary_lines.append(f"标签: {', '.join(d['tags'])}")
                diary_lines.append(f"内容: {d['content_preview']}")
                diary_lines.append("")
            diary_text = "\n".join(diary_lines)
        
        # 构建对话历史摘要
        conv_text = ""
        if conversations:
            conv_lines = [f"- 会话 {c['session_id'][:8]}... ({c['turns']} 轮)" for c in conversations[:3]]
            conv_text = "\n".join(conv_lines)
        
        return f"""分析用户的日记和对话历史，提取用户的个人信息。

规则：
1. 只提取明确提到的信息，不要猜测
2. 如果用户说"我叫子蒙"，提取 name="子蒙"
3. 如果用户说"我是一名工程师"，提取 occupation="工程师"
4. 如果用户说"喜欢阅读"，提取 hobbies=["阅读"]
5. 如果没有新信息，返回空对象 {{}}
6. 不要覆盖已有信息，只补充新信息

当前已知的用户信息：
```json
{json.dumps(profile_info, ensure_ascii=False, indent=2)}
```

最近日记：
{diary_text or "无"}

最近对话历史：
{conv_text or "无"}

上次提取时间：{last_extraction or "从未"}

请提取新的用户信息，以 JSON 格式返回：
{{
    "name": "名字",
    "nickname": "昵称", 
    "occupation": "职业",
    "location": "所在地",
    "company": "公司",
    "skills": ["技能1", "技能2"],
    "hobbies": ["爱好1", "爱好2"],
    "life_goals": ["目标1"],
    "education": "教育背景",
    "family_info": "家庭信息"
}}

只返回 JSON，不要其他内容。"""

    def start_extraction(
        self,
        llm_manager,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ):
        """启动异步提取（后台线程，不阻塞）
        
        Args:
            llm_manager: LLM 管理器
            on_complete: 完成回调，接收提取结果
            on_status: 状态更新回调，接收状态消息
        """
        if self._is_extracting:
            return  # 已经在提取中
            
        self._is_extracting = True
        self._on_status_update = on_status
        
        def _extract_worker():
            try:
                result = self._extract_with_llm(llm_manager)
                self._extraction_result = result
                if on_complete:
                    on_complete(result)
            except Exception:
                self._extraction_result = {}
                if on_complete:
                    on_complete({})
            finally:
                self._is_extracting = False
                self._on_status_update = None
        
        self._extraction_thread = threading.Thread(target=_extract_worker, daemon=True)
        self._extraction_thread.start()
    
    def _extract_with_llm_once(self, llm_manager) -> Dict[str, Any]:
        """单次 LLM 提取（内部方法）"""
        from huaqi_src.core.llm import Message
        
        # 收集数据
        user_data = self._collect_user_data()
        
        # 构建提示词
        prompt = self._build_extraction_prompt(user_data)
        
        messages = [
            Message.system("你是用户信息分析助手，从日记和对话中提取结构化信息。"),
            Message.user(prompt)
        ]
        
        response = llm_manager.chat(messages)
        content = response.content.strip()
        
        # 清理 markdown 代码块
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
        
        # 过滤空值和无效值
        extracted = {k: v for k, v in extracted.items() if v and v not in ([], "", None, "null")}
        
        # 确保列表字段是列表
        list_fields = ['skills', 'hobbies', 'life_goals', 'values']
        for field in list_fields:
            if field in extracted and isinstance(extracted[field], str):
                extracted[field] = [extracted[field]]
        
        # 应用到用户画像
        if extracted:
            profile_manager = get_profile_manager()
            profile_manager._apply_extraction(extracted, "startup_analysis")
        
        return extracted

    def _extract_with_llm(self, llm_manager) -> Dict[str, Any]:
        """使用 LLM 提取用户信息（带重试机制）
        
        失败后会自动重试，直到成功或达到最大重试次数。
        使用指数退避策略减少 API 压力。
        """
        self._retry_count = 0
        self._last_error = None
        
        while self._retry_count < self.MAX_RETRIES:
            try:
                self._notify_status(f"正在分析用户数据... (尝试 {self._retry_count + 1}/{self.MAX_RETRIES})")
                
                result = self._extract_with_llm_once(llm_manager)
                
                # 成功
                if result:
                    self._notify_status(f"✓ 已提取: {', '.join(result.keys())}")
                    return result
                else:
                    self._notify_status("✓ 分析完成，无新信息")
                    return {}
                    
            except Exception as e:
                self._last_error = str(e)
                self._retry_count += 1
                
                if self._retry_count < self.MAX_RETRIES:
                    # 计算退避延迟：2s, 4s, 8s...
                    delay = self.RETRY_DELAY_BASE * (2 ** (self._retry_count - 1))
                    self._notify_status(f"提取失败，{delay:.0f}秒后重试... ({self._retry_count}/{self.MAX_RETRIES})")
                    
                    # 使用带中断检查的睡眠
                    for _ in range(int(delay * 10)):
                        if not self._is_extracting:  # 检查是否被取消
                            return {}
                        import time
                        time.sleep(0.1)
                else:
                    # 达到最大重试次数
                    self._notify_status(f"✗ 提取失败，已达到最大重试次数 ({self.MAX_RETRIES})")
                    break
        
        # 所有重试都失败，尝试兜底方案
        self._notify_status("切换到兜底方案...")
        fallback_result = self._extract_with_fallback()
        if fallback_result:
            self._notify_status(f"✓ 兜底方案提取: {', '.join(fallback_result.keys())}")
        else:
            self._notify_status("✓ 兜底方案无新信息")
        return fallback_result
    
    def _extract_with_fallback(self) -> Dict[str, Any]:
        """兜底提取方案：基于规则的关键词匹配
        
        当 LLM 提取失败时，使用简单的规则匹配从日记和对话中提取信息。
        虽然准确率不如 LLM，但不会依赖外部 API。
        """
        extracted = {}
        
        # 1. 从日记内容提取
        try:
            diary_data = self._collect_user_data().get("recent_diaries", [])
            for diary in diary_data:
                content = diary.get("content_preview", "")
                
                # 匹配 "我是XXX"、"我叫XXX"
                patterns = [
                    (r'我是([\u4e00-\u9fa5]{2,4})', 'name'),
                    (r'我叫([\u4e00-\u9fa5]{2,4})', 'name'),
                    (r'昵称[是为]?([\u4e00-\u9fa5\w]{1,6})', 'nickname'),
                    (r'([\u4e00-\u9fa5]{2,6})工程师', 'occupation'),
                    (r'职业[是为]([^，。]{2,10})', 'occupation'),
                    (r'住在([^，。]{2,10})', 'location'),
                    (r'([^，。]{2,6})人', 'location'),
                    (r'在([^，。]{2,10})工作', 'company'),
                    (r'公司[是为]([^，。]{2,10})', 'company'),
                    (r'我会([\u4e00-\u9fa5\w\s,]+)', 'skills'),
                    (r'擅长([\u4e00-\u9fa5\w\s,]+)', 'skills'),
                    (r'喜欢([\u4e00-\u9fa5\w\s,]+)', 'hobbies'),
                    (r'爱好([\u4e00-\u9fa5\w\s,]+)', 'hobbies'),
                ]
                
                for pattern, field in patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        value = matches[0].strip()
                        if value and len(value) >= 2:
                            if field in ['skills', 'hobbies']:
                                # 列表字段，分割逗号
                                items = [v.strip() for v in re.split(r'[,，、和]', value) if len(v.strip()) >= 2]
                                if items:
                                    extracted[field] = list(set(extracted.get(field, []) + items))
                            else:
                                extracted[field] = value
        except Exception:
            pass
        
        # 2. 应用提取结果
        if extracted:
            try:
                profile_manager = get_profile_manager()
                profile_manager._apply_extraction(extracted, "fallback_analysis")
            except Exception:
                pass
        
        return extracted
    
    def is_extracting(self) -> bool:
        """检查是否正在提取"""
        return self._is_extracting
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """获取提取结果（可能为 None 表示还在提取中）"""
        return self._extraction_result
    
    def get_retry_count(self) -> int:
        """获取已重试次数"""
        return self._retry_count
    
    def get_last_error(self) -> Optional[str]:
        """获取最后一次错误信息"""
        return self._last_error
    
    def cancel_extraction(self):
        """取消当前提取（ gracefully ）"""
        self._is_extracting = False
        if self._extraction_thread and self._extraction_thread.is_alive():
            # 等待线程自然结束（由 _is_extracting 标志控制）
            self._extraction_thread.join(timeout=1.0)
    
    def wait_for_completion(self, timeout: float = 60.0) -> Dict[str, Any]:
        """等待提取完成（阻塞，带超时）
        
        注意：由于有重试机制，建议设置较长的超时时间。
        最大等待时间 = 每次超时 * (MAX_RETRIES + 重试延迟)
        例如：30s * 3 + (2+4)s ≈ 100s
        
        Args:
            timeout: 超时时间（秒），默认60秒
            
        Returns:
            提取结果（超时返回空字典）
        """
        if self._extraction_thread and self._extraction_thread.is_alive():
            self._extraction_thread.join(timeout=timeout)
        return self._extraction_result or {}


# 全局提取器实例
_data_extractor: Optional[UserDataExtractor] = None


def get_data_extractor() -> UserDataExtractor:
    """获取全局数据提取器"""
    global _data_extractor
    if _data_extractor is None:
        _data_extractor = UserDataExtractor()
    return _data_extractor


def init_data_extractor(memory_dir: Optional[Path] = None) -> UserDataExtractor:
    """初始化全局数据提取器"""
    global _data_extractor
    _data_extractor = UserDataExtractor(memory_dir)
    return _data_extractor


def extract_user_info_on_startup(llm_manager, timeout: float = 15.0) -> Dict[str, Any]:
    """启动时提取用户信息（简化调用）
    
    阻塞执行，带超时。适用于启动时需要等待结果的场景。
    
    Args:
        llm_manager: LLM 管理器
        timeout: 超时时间（秒）
        
    Returns:
        提取的用户信息
    """
    extractor = get_data_extractor()
    
    # 已经在提取中，等待结果
    if extractor.is_extracting():
        return extractor.wait_for_completion(timeout)
    
    # 已经提取过，返回缓存结果
    if extractor.get_result() is not None:
        return extractor.get_result()
    
    # 启动提取并等待
    result_container = {}
    def _on_complete(result):
        result_container['result'] = result
    
    extractor.start_extraction(llm_manager, on_complete=_on_complete)
    
    # 等待超时
    extractor.wait_for_completion(timeout)
    
    return result_container.get('result', {}) or extractor.get_result() or {}
