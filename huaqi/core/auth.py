"""用户认证系统

支持 OAuth (GitHub/Google) 认证
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import hashlib
import secrets

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """用户档案"""
    user_id: str
    email: str
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    provider: str  # github, google, local
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    
    # 用户偏好
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


@dataclass
class UserSession:
    """用户会话"""
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    token: str
    
    @classmethod
    def create(cls, user_id: str, duration_hours: int = 168) -> "UserSession":
        """创建新会话（默认7天）"""
        now = datetime.now()
        return cls(
            session_id=secrets.token_hex(16),
            user_id=user_id,
            created_at=now,
            expires_at=now.replace(hour=now.hour + duration_hours),
            token=secrets.token_urlsafe(32)
        )
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class UserManager:
    """用户管理器"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.users_dir = data_dir / "users"
        self.users_dir.mkdir(parents=True, exist_ok=True)
        
        # 会话存储
        self.sessions: Dict[str, UserSession] = {}
    
    def create_user(
        self,
        email: str,
        username: str,
        provider: str,
        provider_id: str,
        **extra
    ) -> UserProfile:
        """创建新用户"""
        # 生成用户ID
        user_id = hashlib.sha256(
            f"{provider}:{provider_id}".encode()
        ).hexdigest()[:16]
        
        # 检查是否已存在
        if self.get_user(user_id):
            raise ValueError(f"用户已存在: {email}")
        
        # 创建用户档案
        profile = UserProfile(
            user_id=user_id,
            email=email,
            username=username,
            provider=provider,
            **extra
        )
        
        # 保存用户数据
        self._save_user(profile)
        
        # 创建用户数据目录
        user_dir = self.get_user_dir(user_id)
        self._init_user_directory(user_dir)
        
        return profile
    
    def get_user(self, user_id: str) -> Optional[UserProfile]:
        """获取用户"""
        user_file = self.users_dir / f"{user_id}.json"
        if not user_file.exists():
            return None
        
        import json
        with open(user_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return UserProfile(**data)
    
    def get_user_by_email(self, email: str) -> Optional[UserProfile]:
        """通过邮箱查找用户"""
        for user_file in self.users_dir.glob("*.json"):
            user = self.get_user(user_file.stem)
            if user and user.email == email:
                return user
        return None
    
    def get_user_dir(self, user_id: str) -> Path:
        """获取用户数据目录"""
        return self.data_dir / "users_data" / user_id
    
    def list_users(self) -> list[UserProfile]:
        """列出所有用户"""
        users = []
        for user_file in self.users_dir.glob("*.json"):
            user = self.get_user(user_file.stem)
            if user:
                users.append(user)
        return users
    
    def delete_user(self, user_id: str, confirm: bool = False) -> bool:
        """删除用户（谨慎！）"""
        if not confirm:
            raise ValueError("删除用户需要 confirm=True")
        
        # 删除用户档案
        user_file = self.users_dir / f"{user_id}.json"
        if user_file.exists():
            user_file.unlink()
        
        # 删除用户数据（可选，可以保留备份）
        user_dir = self.get_user_dir(user_id)
        if user_dir.exists():
            import shutil
            shutil.rmtree(user_dir)
        
        return True
    
    def create_session(self, user_id: str) -> UserSession:
        """创建用户会话"""
        session = UserSession.create(user_id)
        self.sessions[session.session_id] = session
        
        # 更新最后登录时间
        user = self.get_user(user_id)
        if user:
            user.last_login = datetime.now()
            self._save_user(user)
        
        return session
    
    def validate_session(self, token: str) -> Optional[str]:
        """验证会话令牌，返回用户ID"""
        for session in self.sessions.values():
            if session.token == token and not session.is_expired:
                return session.user_id
        return None
    
    def logout(self, session_id: str):
        """登出"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def _save_user(self, profile: UserProfile):
        """保存用户档案"""
        import json
        user_file = self.users_dir / f"{profile.user_id}.json"
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2, default=str)
    
    def _init_user_directory(self, user_dir: Path):
        """初始化用户数据目录结构"""
        # 创建标准目录结构
        (user_dir / "memory" / "identity").mkdir(parents=True, exist_ok=True)
        (user_dir / "memory" / "context" / "session").mkdir(parents=True, exist_ok=True)
        (user_dir / "memory" / "context" / "working").mkdir(parents=True, exist_ok=True)
        (user_dir / "memory" / "context" / "long_term").mkdir(parents=True, exist_ok=True)
        (user_dir / "memory" / "patterns").mkdir(parents=True, exist_ok=True)
        (user_dir / "memory" / "conversations").mkdir(parents=True, exist_ok=True)
        (user_dir / "tasks").mkdir(parents=True, exist_ok=True)
        (user_dir / "templates").mkdir(parents=True, exist_ok=True)
        (user_dir / "config").mkdir(parents=True, exist_ok=True)
        (user_dir / "vectors").mkdir(parents=True, exist_ok=True)
        (user_dir / "sync").mkdir(parents=True, exist_ok=True)
        
        # 创建默认配置文件
        self._create_default_config(user_dir)
    
    def _create_default_config(self, user_dir: Path):
        """创建默认用户配置"""
        import yaml
        
        default_config = {
            "version": "0.1.0",
            "created_at": datetime.now().isoformat(),
            "llm": {
                "default_provider": "claude",
                "providers": {}
            },
            "memory": {
                "max_session_memory": 100,
                "auto_extract_insights": True,
                "sync_enabled": False
            },
            "interface": {
                "default": "cli",
                "theme": "default"
            },
            "security": {
                "encrypt_sensitive": True,
                "session_timeout_hours": 168
            }
        }
        
        config_file = user_dir / "config" / "user.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, allow_unicode=True)


class OAuthHandler:
    """OAuth 认证处理器"""
    
    def __init__(self, user_manager: UserManager):
        self.user_manager = user_manager
    
    def handle_github_callback(self, code: str, client_id: str, client_secret: str) -> UserProfile:
        """处理 GitHub OAuth 回调
        
        Args:
            code: GitHub 返回的授权码
            client_id: GitHub App Client ID
            client_secret: GitHub App Client Secret
            
        Returns:
            UserProfile: 用户档案
        """
        import requests
        
        # 1. 换取 access token
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code
            },
            headers={"Accept": "application/json"}
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise ValueError(f"获取 token 失败: {token_data}")
        
        # 2. 获取用户信息
        user_response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
        )
        github_user = user_response.json()
        
        # 3. 创建或获取用户
        email = github_user.get("email") or f"{github_user['login']}@github.local"
        
        # 检查是否已存在
        existing_user = self.user_manager.get_user_by_email(email)
        if existing_user:
            return existing_user
        
        # 创建新用户
        return self.user_manager.create_user(
            email=email,
            username=github_user["login"],
            provider="github",
            provider_id=str(github_user["id"]),
            display_name=github_user.get("name"),
            avatar_url=github_user.get("avatar_url")
        )
    
    def handle_google_callback(self, code: str, client_id: str, client_secret: str, redirect_uri: str) -> UserProfile:
        """处理 Google OAuth 回调"""
        import requests
        
        # 1. 换取 access token
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri
            }
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise ValueError(f"获取 token 失败: {token_data}")
        
        # 2. 获取用户信息
        user_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        google_user = user_response.json()
        
        # 3. 创建或获取用户
        email = google_user["email"]
        
        # 检查是否已存在
        existing_user = self.user_manager.get_user_by_email(email)
        if existing_user:
            return existing_user
        
        # 创建新用户
        return self.user_manager.create_user(
            email=email,
            username=email.split("@")[0],
            provider="google",
            provider_id=google_user["id"],
            display_name=google_user.get("name"),
            avatar_url=google_user.get("picture")
        )
