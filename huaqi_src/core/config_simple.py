"""简化配置管理 - 单用户模式

所有配置存储在 memory/ 目录下，便于 Git 管理
"""

from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
import yaml

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
    search_algorithm: str = "hybrid"
    search_top_k: int = 5


class AppConfig(BaseModel):
    """应用配置"""
    version: str = "0.1.0"
    
    # 数据目录配置（保存上次使用的数据目录）
    data_dir: Optional[str] = None
    
    # LLM 配置
    llm_default_provider: str = "dummy"
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict)
    
    # 记忆配置
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    
    # 界面配置
    interface_theme: str = "default"
    interface_language: str = "zh"
    
    # 自定义设置
    custom: Dict[str, Any] = Field(default_factory=dict)


class ConfigManager:
    """配置管理器 - 单用户模式
    
    所有配置存储在 memory/config.yaml
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.memory_dir = data_dir / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_path = self.memory_dir / "config.yaml"
        self._config: Optional[AppConfig] = None
    
    def load_config(self) -> AppConfig:
        """加载配置"""
        if self._config is not None:
            return self._config
        
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self._config = AppConfig(**data)
        else:
            # 创建默认配置
            self._config = AppConfig()
            self.save_config()
        
        return self._config
    
    def save_config(self):
        """保存配置"""
        if self._config is None:
            self._config = AppConfig()
        
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._config.model_dump(), f, allow_unicode=True, default_flow_style=False)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        config = self.load_config()
        keys = key.split(".")
        value = config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            elif hasattr(value, k):
                value = getattr(value, k)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """设置配置项"""
        config = self.load_config()
        keys = key.split(".")
        target = config
        
        for k in keys[:-1]:
            if isinstance(target, dict):
                target = target.setdefault(k, {})
            elif hasattr(target, k):
                target = getattr(target, k)
        
        final_key = keys[-1]
        if isinstance(target, dict):
            target[final_key] = value
        elif hasattr(target, final_key):
            setattr(target, final_key, value)
        
        self.save_config()


def init_config_manager(data_dir: Path) -> ConfigManager:
    """初始化配置管理器"""
    return ConfigManager(data_dir)
