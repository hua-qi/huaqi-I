"""配置热重载

监听配置文件变化，自动重载配置并通知订阅者
"""

import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Set
from dataclasses import dataclass
from enum import Enum

from .manager import ConfigManager


class ConfigChangeType(Enum):
    """配置变化类型"""
    LLM = "llm"               # LLM 配置变化
    MEMORY = "memory"         # 记忆配置变化
    INTERFACE = "interface"   # 界面配置变化
    CUSTOM = "custom"         # 自定义配置变化
    ALL = "all"               # 全部变化


@dataclass
class ConfigChangeEvent:
    """配置变化事件"""
    change_type: ConfigChangeType
    key: str
    old_value: any
    new_value: any
    timestamp: float


class ConfigHotReload:
    """配置热重载管理器
    
    功能:
    - 监听配置文件变化
    - 自动重载配置
    - 通知订阅者
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        poll_interval: float = 1.0,
    ):
        self.config_manager = config_manager
        self.poll_interval = poll_interval
        
        self._running = False
        self._thread: threading.Thread = None
        self._last_mtime: float = 0
        self._callbacks: Dict[ConfigChangeType, List[Callable]] = {
            ct: [] for ct in ConfigChangeType
        }
        self._last_config: dict = None
    
    def start(self):
        """启动热重载监听"""
        if self._running:
            return
        
        self._running = True
        self._last_mtime = self._get_config_mtime()
        self._last_config = self._get_config_dict()
        
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        
        print("[ConfigHotReload] 热重载监听已启动")
    
    def stop(self):
        """停止热重载监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[ConfigHotReload] 热重载监听已停止")
    
    def _watch_loop(self):
        """监听循环"""
        while self._running:
            try:
                self._check_and_reload()
            except Exception as e:
                print(f"[ConfigHotReload] 检查配置失败: {e}")
            
            time.sleep(self.poll_interval)
    
    def _get_config_mtime(self) -> float:
        """获取配置文件修改时间"""
        if self.config_manager.config_path.exists():
            return self.config_manager.config_path.stat().st_mtime
        return 0
    
    def _get_config_dict(self) -> dict:
        """获取配置字典"""
        config = self.config_manager.load_config()
        return config.model_dump()
    
    def _check_and_reload(self):
        """检查并重载配置"""
        current_mtime = self._get_config_mtime()
        
        if current_mtime <= self._last_mtime:
            return
        
        # 读取新配置
        try:
            new_config = self._get_config_dict()
            changes = self._detect_changes(self._last_config, new_config)
            
            # 更新配置管理器
            self.config_manager._config = self.config_manager.load_config()
            
            # 通知订阅者
            for change in changes:
                self._notify(change)
            
            self._last_config = new_config
            self._last_mtime = current_mtime
            
            print(f"[ConfigHotReload] 配置已重载，检测到 {len(changes)} 处变化")
            
        except Exception as e:
            print(f"[ConfigHotReload] 重载配置失败: {e}")
    
    def _detect_changes(
        self,
        old_config: dict,
        new_config: dict,
        prefix: str = "",
    ) -> List[ConfigChangeEvent]:
        """检测配置变化"""
        changes = []
        timestamp = time.time()
        
        all_keys = set(old_config.keys()) | set(new_config.keys())
        
        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_val = old_config.get(key)
            new_val = new_config.get(key)
            
            if old_val != new_val:
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    # 递归检测子变化
                    changes.extend(
                        self._detect_changes(old_val, new_val, full_key)
                    )
                else:
                    # 确定变化类型
                    change_type = self._get_change_type(full_key)
                    
                    changes.append(ConfigChangeEvent(
                        change_type=change_type,
                        key=full_key,
                        old_value=old_val,
                        new_value=new_val,
                        timestamp=timestamp,
                    ))
        
        return changes
    
    def _get_change_type(self, key: str) -> ConfigChangeType:
        """根据 key 确定变化类型"""
        if key.startswith("llm"):
            return ConfigChangeType.LLM
        elif key.startswith("memory"):
            return ConfigChangeType.MEMORY
        elif key.startswith("interface"):
            return ConfigChangeType.INTERFACE
        elif key.startswith("custom"):
            return ConfigChangeType.CUSTOM
        else:
            return ConfigChangeType.ALL
    
    def _notify(self, event: ConfigChangeEvent):
        """通知订阅者"""
        # 通知特定类型订阅者
        for callback in self._callbacks.get(event.change_type, []):
            try:
                callback(event)
            except Exception as e:
                print(f"[ConfigHotReload] 回调执行失败: {e}")
        
        # 通知全局订阅者
        for callback in self._callbacks.get(ConfigChangeType.ALL, []):
            try:
                callback(event)
            except Exception as e:
                print(f"[ConfigHotReload] 回调执行失败: {e}")
    
    def on_change(
        self,
        change_type: ConfigChangeType,
        callback: Callable[[ConfigChangeEvent], None],
    ):
        """订阅配置变化
        
        Args:
            change_type: 订阅的变化类型
            callback: 回调函数，接收 ConfigChangeEvent
        """
        if change_type not in self._callbacks:
            self._callbacks[change_type] = []
        self._callbacks[change_type].append(callback)
    
    def off_change(
        self,
        change_type: ConfigChangeType,
        callback: Callable[[ConfigChangeEvent], None],
    ):
        """取消订阅"""
        if change_type in self._callbacks:
            if callback in self._callbacks[change_type]:
                self._callbacks[change_type].remove(callback)


# 全局实例
_config_hot_reload: ConfigHotReload = None


def init_hot_reload(config_manager: ConfigManager) -> ConfigHotReload:
    """初始化热重载"""
    global _config_hot_reload
    _config_hot_reload = ConfigHotReload(config_manager)
    _config_hot_reload.start()
    return _config_hot_reload


def get_hot_reload() -> ConfigHotReload:
    """获取热重载实例"""
    return _config_hot_reload


def on_config_change(
    change_type: ConfigChangeType = ConfigChangeType.ALL,
    callback: Callable[[ConfigChangeEvent], None] = None,
):
    """装饰器：订阅配置变化
    
    示例:
        @on_config_change(ConfigChangeType.LLM)
        def on_llm_change(event):
            print(f"LLM配置变化: {event.key}")
    """
    def decorator(func):
        if _config_hot_reload:
            _config_hot_reload.on_change(change_type, func)
        return func
    
    if callback is None:
        return decorator
    else:
        return decorator(callback)
