"""配置管理系统

支持多用户隔离的配置管理
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import yaml
import json
from functools import lru_cache

from pydantic import BaseModel, Field


class LLMProviderConfig(BaseModel):
    """LLM 提供商配置"""
    name: str
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4000


class MemoryConfig(BaseModel):
    """记忆系统配置"""
    max_session_memory: int = 100
    max_working_memory: int = 50
    auto_extract_insights: bool = True
    importance_threshold: float = 0.6
    embedding_model: str = "text-embedding-3-small"
    vector_db_path: str = "vectors/"


class SyncConfig(BaseModel):
    """同步配置"""
    enabled: bool = False
    provider: str = "github"  # github, s3, webdav
    auto_sync: bool = False
    sync_interval_minutes: int = 60
    github_repo: Optional[str] = None
    github_branch: str = "main"


class UserConfig(BaseModel):
    """用户配置"""
    version: str = "0.1.0"
    user_id: str
    
    # LLM 配置
    llm_default_provider: str = "claude"
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict)
    
    # 记忆配置
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    
    # 同步配置
    sync: SyncConfig = Field(default_factory=SyncConfig)
    
    # 界面配置
    interface_theme: str = "default"
    interface_language: str = "zh"
    
    # 安全配置
    encrypt_sensitive: bool = True
    session_timeout_hours: int = 168
    
    # 自定义设置
    custom: Dict[str, Any] = Field(default_factory=dict)


class ConfigManager:
    """配置管理器
    
    支持多用户隔离，每个用户有独立的配置
    """
    
    def __init__(self, data_dir: Path, user_id: Optional[str] = None):
        self.data_dir = data_dir
        self.user_id = user_id
        
        # 全局配置目录
        self.global_config_dir = data_dir / "config"
        self.global_config_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前用户配置
        self._current_config: Optional[UserConfig] = None
        
        if user_id:
            self.switch_user(user_id)
    
    @property
    def current_user_id(self) -> Optional[str]:
        """获取当前用户ID"""
        return self.user_id
    
    @property
    def is_global_mode(self) -> bool:
        """是否处于全局模式（未登录）"""
        return self.user_id is None
    
    def switch_user(self, user_id: str):
        """切换用户"""
        self.user_id = user_id
        self._current_config = None  # 清除缓存
        self._ensure_user_config_exists()
    
    def get_user_config_path(self, user_id: Optional[str] = None) -> Path:
        """获取用户配置文件路径"""
        uid = user_id or self.user_id
        if not uid:
            raise ValueError("未指定用户")
        
        user_dir = self.data_dir / "users_data" / uid / "config"
        return user_dir / "user.yaml"
    
    def load_config(self, user_id: Optional[str] = None) -> UserConfig:
        """加载配置"""
        uid = user_id or self.user_id
        
        if uid is None:
            raise ValueError("未指定用户，请先登录")
        
        # 如果有缓存且是当前用户，直接返回
        if self._current_config and self.user_id == uid:
            return self._current_config
        
        config_path = self.get_user_config_path(uid)
        
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                config = UserConfig(**data)
        else:
            # 创建默认配置
            config = UserConfig(user_id=uid)
            self.save_config(config)
        
        if uid == self.user_id:
            self._current_config = config
        
        return config
    
    def save_config(self, config: UserConfig, user_id: Optional[str] = None):
        """保存配置"""
        uid = user_id or self.user_id
        if uid is None:
            raise ValueError("未指定用户")
        
        config_path = self.get_user_config_path(uid)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config.model_dump(), f, allow_unicode=True, default_flow_style=False)
        
        if uid == self.user_id:
            self._current_config = config
    
    def get(self, key: str, default: Any = None, user_id: Optional[str] = None) -> Any:
        """获取配置项"""
        config = self.load_config(user_id)
        
        # 支持点号访问，如 "llm.temperature"
        keys = key.split(".")
        value = config
        
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            elif isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any, user_id: Optional[str] = None):
        """设置配置项"""
        config = self.load_config(user_id)
        
        # 支持点号访问
        keys = key.split(".")
        target = config
        
        for k in keys[:-1]:
            if hasattr(target, k):
                target = getattr(target, k)
            elif isinstance(target, dict) and k in target:
                target = target[k]
            else:
                raise KeyError(f"配置项不存在: {key}")
        
        final_key = keys[-1]
        if hasattr(target, final_key):
            setattr(target, final_key, value)
        elif isinstance(target, dict):
            target[final_key] = value
        else:
            raise KeyError(f"无法设置配置项: {key}")
        
        self.save_config(config, user_id)
    
    def add_llm_provider(self, provider: LLMProviderConfig, user_id: Optional[str] = None):
        """添加 LLM 提供商"""
        config = self.load_config(user_id)
        config.llm_providers[provider.name] = provider
        self.save_config(config, user_id)
    
    def remove_llm_provider(self, name: str, user_id: Optional[str] = None):
        """移除 LLM 提供商"""
        config = self.load_config(user_id)
        if name in config.llm_providers:
            del config.llm_providers[name]
            self.save_config(config, user_id)
    
    def list_llm_providers(self, user_id: Optional[str] = None) -> List[str]:
        """列出所有 LLM 提供商"""
        config = self.load_config(user_id)
        return list(config.llm_providers.keys())
    
    def get_active_llm_config(self, user_id: Optional[str] = None) -> Optional[LLMProviderConfig]:
        """获取当前激活的 LLM 配置"""
        config = self.load_config(user_id)
        return config.llm_providers.get(config.llm_default_provider)
    
    def get_user_data_dir(self, user_id: Optional[str] = None) -> Path:
        """获取用户数据目录"""
        uid = user_id or self.user_id
        if uid is None:
            raise ValueError("未指定用户")
        return self.data_dir / "users_data" / uid
    
    def get_user_memory_dir(self, user_id: Optional[str] = None) -> Path:
        """获取用户记忆目录"""
        return self.get_user_data_dir(user_id) / "memory"
    
    def get_user_vector_dir(self, user_id: Optional[str] = None) -> Path:
        """获取用户向量库目录"""
        return self.get_user_data_dir(user_id) / "vectors"
    
    def _ensure_user_config_exists(self):
        """确保当前用户的配置文件存在"""
        if self.user_id:
            try:
                self.load_config(self.user_id)
            except:
                # 创建默认配置
                config = UserConfig(user_id=self.user_id)
                self.save_config(config)
    
    # 全局配置（系统级）
    
    def get_global_config(self) -> Dict[str, Any]:
        """获取全局配置"""
        global_config_path = self.global_config_dir / "system.yaml"
        
        if global_config_path.exists():
            with open(global_config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def set_global_config(self, key: str, value: Any):
        """设置全局配置"""
        config = self.get_global_config()
        config[key] = value
        
        global_config_path = self.global_config_dir / "system.yaml"
        with open(global_config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)
    
    def get_all_users(self) -> List[str]:
        """获取所有用户ID"""
        users_data_dir = self.data_dir / "users_data"
        if not users_data_dir.exists():
            return []
        
        return [d.name for d in users_data_dir.iterdir() if d.is_dir()]


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def init_config_manager(data_dir: Path, user_id: Optional[str] = None) -> ConfigManager:
    """初始化全局配置管理器"""
    global _config_manager
    _config_manager = ConfigManager(data_dir, user_id)
    return _config_manager


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器"""
    if _config_manager is None:
        raise RuntimeError("配置管理器未初始化")
    return _config_manager
