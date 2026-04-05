"""CLI 共享上下文

全局组件实例和 ensure_initialized 初始化逻辑。
"""

import os
from pathlib import Path
from typing import Optional

from rich.console import Console

from huaqi_src.config.manager import init_config_manager, ConfigManager
from huaqi_src.config.paths import require_data_dir, get_memory_dir
from huaqi_src.layers.capabilities.personality import PersonalityEngine
from huaqi_src.layers.capabilities.hooks import HookManager
from huaqi_src.layers.capabilities.growth import GrowthTracker
from huaqi_src.layers.data.diary import DiaryStore
from huaqi_src.layers.data.git.auto_commit import GitAutoCommit
from huaqi_src.layers.capabilities.llm.manager import LLMConfig, Message, LLMManager
from huaqi_src.layers.data.memory.storage.markdown_store import MarkdownMemoryStore
from huaqi_src.scheduler.startup_recovery import StartupJobRecovery
from huaqi_src.scheduler.jobs import _DEFAULT_JOB_CONFIGS

console = Console()

DATA_DIR: Optional[Path] = None
MEMORY_DIR: Optional[Path] = None

_config: Optional[ConfigManager] = None
_personality: Optional[PersonalityEngine] = None
_hooks: Optional[HookManager] = None
_growth: Optional[GrowthTracker] = None
_diary: Optional[DiaryStore] = None
_memory_store: Optional[MarkdownMemoryStore] = None
_git: Optional[GitAutoCommit] = None


def ensure_initialized():
    """确保核心组件已初始化"""
    global _config, _personality, _hooks, _growth, _diary, _memory_store, _git
    global DATA_DIR, MEMORY_DIR

    DATA_DIR = require_data_dir()
    MEMORY_DIR = get_memory_dir()

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    if _config is None:
        _config = init_config_manager(DATA_DIR)
    if _personality is None:
        _personality = PersonalityEngine(MEMORY_DIR)
    if _hooks is None:
        _git = GitAutoCommit(DATA_DIR)
        _hooks = HookManager(MEMORY_DIR, git_committer=_git)
    if _growth is None:
        _growth = GrowthTracker(MEMORY_DIR, git_committer=_git)
    if _diary is None:
        _diary = DiaryStore(MEMORY_DIR, git_committer=_git)
    if _memory_store is None:
        _memory_store = MarkdownMemoryStore(MEMORY_DIR / "conversations")

    _run_startup_recovery()


def _run_startup_recovery():
    try:
        from huaqi_src.config.paths import get_scheduler_db_path
        db_path = get_scheduler_db_path()
        recovery = StartupJobRecovery(
            data_dir=DATA_DIR,
            db_path=db_path,
            job_configs=_DEFAULT_JOB_CONFIGS,
        )
        recovery.run(notify_callback=_on_recovery_notify)
    except Exception as e:
        print(f"[Recovery] 启动检查失败: {e}")


def _on_recovery_notify(missed_jobs):
    names = "、".join(m.display_name for m in missed_jobs)
    console.print(f"[yellow]⚠️  发现 {len(missed_jobs)} 个任务未执行（{names}），正在后台补跑...[/yellow]")


def build_llm_manager(temperature: float = 0.7, max_tokens: int = 1500, timeout: int = 60) -> Optional[LLMManager]:
    """构建 LLM 管理器（通用工厂）"""
    if _config is None:
        return None
    config = _config.load_config()
    provider_name = config.llm_default_provider
    if provider_name not in config.llm_providers:
        return None
    provider_config = config.llm_providers[provider_name]
    api_key = provider_config.api_key or os.environ.get("WQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
    llm = LLMManager()
    llm_config = LLMConfig(
        provider=provider_config.name,
        model=provider_config.model,
        api_key=api_key,
        api_base=provider_config.api_base,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    llm.add_config(llm_config)
    llm.set_active(provider_config.name)
    return llm
