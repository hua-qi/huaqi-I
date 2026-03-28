"""核心业务逻辑模块

包含配置管理、用户模型、LLM 封装、分析引擎、记忆存储等核心功能。
"""

from .config_paths import (
    get_data_dir,
    set_data_dir,
    get_memory_dir,
    require_data_dir,
    get_vector_db_dir,
)
from .config_simple import (
    ConfigManager,
    LLMProviderConfig,
    init_config_manager,
)
from .config_hot_reload import (
    get_hot_reload,
    init_hot_reload,
)
from .llm import (
    LLMConfig,
    LLMManager,
    Message,
    get_llm_manager,
)
from .ui_utils import (
    HuaqiUI,
    HuaqiTheme,
    get_ui,
)
from .personality_simple import PersonalityEngine
from .personality_updater import PersonalityUpdater
from .hooks_simple import HookManager
from .growth_simple import GrowthTracker
from .diary_simple import DiaryStore
from .git_auto_commit import GitAutoCommit
from .profile_models import (
    UserIdentity,
    UserPreferences,
    UserBackground,
    UserProfile,
)
from .profile_manager import (
    UserProfileManager,
    get_profile_manager,
    init_profile_manager,
)
from .profile_narrative import (
    ProfileNarrative,
    ProfileNarrativeManager,
    get_narrative_manager,
)
from .profile_extractor import (
    UserDataExtractor,
    get_data_extractor,
    init_data_extractor,
)
from .pattern_learning import get_pattern_engine
from .proactive_care import get_care_engine
from .adaptive_understanding import get_adaptive_understanding

__all__ = [
    # 配置路径
    "get_data_dir",
    "set_data_dir",
    "get_memory_dir",
    "require_data_dir",
    "get_vector_db_dir",
    # 配置管理
    "ConfigManager",
    "LLMProviderConfig",
    "init_config_manager",
    # 配置热重载
    "get_hot_reload",
    "init_hot_reload",
    # LLM
    "LLMConfig",
    "LLMManager",
    "Message",
    "get_llm_manager",
    # UI 工具
    "HuaqiUI",
    "HuaqiTheme",
    "get_ui",
    # 个性系统
    "PersonalityEngine",
    "PersonalityUpdater",
    # 成长与钩子
    "HookManager",
    "GrowthTracker",
    # 存储
    "DiaryStore",
    "GitAutoCommit",
    # 用户画像模型
    "UserIdentity",
    "UserPreferences",
    "UserBackground",
    "UserProfile",
    # 用户画像管理器
    "UserProfileManager",
    "get_profile_manager",
    "init_profile_manager",
    # 叙事生成
    "ProfileNarrative",
    "ProfileNarrativeManager",
    "get_narrative_manager",
    # 数据提取
    "UserDataExtractor",
    "get_data_extractor",
    "init_data_extractor",
    # 分析与学习
    "get_pattern_engine",
    "get_care_engine",
    "get_adaptive_understanding",
]
