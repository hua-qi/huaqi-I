"""Hook 系统

Hooks 定义存储在 memory/hooks.yaml
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pathlib import Path
import yaml


class TriggerType(Enum):
    SCHEDULE = "schedule"
    EVENT = "event"
    CONDITION = "condition"


class EventType(Enum):
    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_ENDED = "conversation_ended"
    MEMORY_CREATED = "memory_created"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class Hook:
    """Hook 定义"""
    id: str
    name: str
    description: str
    trigger_type: TriggerType
    trigger_config: Dict[str, Any]
    actions: List[Dict[str, Any]]
    enabled: bool = True
    last_triggered: Optional[str] = None
    trigger_count: int = 0


class HookManager:
    """Hook 管理器 - 单用户"""

    DEFAULT_HOOKS = [
        {
            "id": "morning-greeting",
            "name": "晨间问候",
            "description": "每天早上 9 点发送问候",
            "trigger_type": "schedule",
            "trigger_config": {"type": "daily", "time": "09:00"},
            "actions": [{"type": "send_message", "params": {"message": "早安！今天有什么计划？"}}],
        },
        {
            "id": "daily-summary",
            "name": "每日总结",
            "description": "晚上 10 点生成今日回顾",
            "trigger_type": "schedule",
            "trigger_config": {"type": "daily", "time": "22:00"},
            "actions": [{"type": "send_message", "params": {"message": "今天过得怎么样？"}}],
        },
    ]

    def __init__(self, memory_dir: Path, git_committer=None):
        self.memory_dir = memory_dir
        self.hooks_path = memory_dir / "hooks.yaml"
        self.hooks: Dict[str, Hook] = {}
        self._git_committer = git_committer
        self._load()

    def _load(self):
        """加载 Hooks"""
        if self.hooks_path.exists():
            with open(self.hooks_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                for hook_data in data.get("hooks", []):
                    hook = Hook(**hook_data)
                    self.hooks[hook.id] = hook
        else:
            self._init_defaults()

    def _init_defaults(self):
        """初始化默认 Hooks"""
        for hook_data in self.DEFAULT_HOOKS:
            hook = Hook(**hook_data)
            self.hooks[hook.id] = hook
        self.save()

    def save(self):
        """保存 Hooks"""
        data = {"hooks": [self._hook_to_dict(h) for h in self.hooks.values()]}
        with open(self.hooks_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

    def _hook_to_dict(self, hook: Hook) -> Dict:
        return {
            "id": hook.id,
            "name": hook.name,
            "description": hook.description,
            "trigger_type": hook.trigger_type.value if isinstance(hook.trigger_type, TriggerType) else hook.trigger_type,
            "trigger_config": hook.trigger_config,
            "actions": hook.actions,
            "enabled": hook.enabled,
            "last_triggered": hook.last_triggered,
            "trigger_count": hook.trigger_count,
        }

    def _auto_commit(self, action: str, hook_name: str):
        """自动提交到 git"""
        if self._git_committer:
            self._git_committer.commit_hook_change(hook_name, action)

    def list_hooks(self) -> List[Hook]:
        """列出所有 Hooks"""
        return list(self.hooks.values())

    def get_hook(self, hook_id: str) -> Optional[Hook]:
        """获取 Hook"""
        return self.hooks.get(hook_id)

    def create_hook(self, hook: Hook) -> bool:
        """创建 Hook"""
        if hook.id in self.hooks:
            return False
        self.hooks[hook.id] = hook
        self.save()
        self._auto_commit("create", hook.name)
        return True

    def update_hook(self, hook_id: str, **kwargs) -> bool:
        """更新 Hook"""
        if hook_id not in self.hooks:
            return False

        hook = self.hooks[hook_id]
        hook_name = hook.name
        for key, value in kwargs.items():
            if hasattr(hook, key):
                setattr(hook, key, value)

        self.save()
        self._auto_commit("update", hook_name)
        return True

    def delete_hook(self, hook_id: str) -> bool:
        """删除 Hook"""
        if hook_id not in self.hooks:
            return False
        hook_name = self.hooks[hook_id].name
        del self.hooks[hook_id]
        self.save()
        self._auto_commit("delete", hook_name)
        return True

    def enable(self, hook_id: str):
        """启用 Hook"""
        self.update_hook(hook_id, enabled=True)

    def disable(self, hook_id: str):
        """禁用 Hook"""
        self.update_hook(hook_id, enabled=False)
