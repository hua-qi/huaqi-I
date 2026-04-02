"""配置管理模块

包含路径管理、配置读写、热重载功能。
"""

from .paths import (
    get_data_dir,
    set_data_dir,
    save_data_dir_to_config,
    require_data_dir,
    is_data_dir_set,
    get_memory_dir,
    get_drafts_dir,
    get_vector_db_dir,
    get_models_cache_dir,
    get_pending_reviews_dir,
    get_learning_dir,
    get_diary_dir,
    get_conversations_dir,
    get_work_docs_dir,
    get_cli_chats_dir,
    get_wechat_dir,
    get_inbox_work_docs_dir,
    get_wechat_db_dir,
    get_people_dir,
    get_world_dir,
    get_scheduler_db_path,
    ensure_dirs,
)
from .manager import (
    AppConfig,
    LLMProviderConfig,
    MemoryConfig,
    ConfigManager,
    init_config_manager,
)
from .hot_reload import (
    ConfigChangeType,
    ConfigChangeEvent,
    ConfigHotReload,
    init_hot_reload,
    get_hot_reload,
    on_config_change,
)

__all__ = [
    # 路径管理
    "get_data_dir",
    "set_data_dir",
    "save_data_dir_to_config",
    "require_data_dir",
    "is_data_dir_set",
    "get_memory_dir",
    "get_drafts_dir",
    "get_vector_db_dir",
    "get_models_cache_dir",
    "get_pending_reviews_dir",
    "get_learning_dir",
    "get_diary_dir",
    "get_conversations_dir",
    "get_work_docs_dir",
    "get_cli_chats_dir",
    "get_wechat_dir",
    "get_inbox_work_docs_dir",
    "get_wechat_db_dir",
    "get_people_dir",
    "get_world_dir",
    "get_scheduler_db_path",
    "ensure_dirs",
    # 配置管理
    "AppConfig",
    "LLMProviderConfig",
    "MemoryConfig",
    "ConfigManager",
    "init_config_manager",
    # 热重载
    "ConfigChangeType",
    "ConfigChangeEvent",
    "ConfigHotReload",
    "init_hot_reload",
    "get_hot_reload",
    "on_config_change",
]
