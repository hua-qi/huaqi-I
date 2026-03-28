"""用户画像模块（向后兼容入口）

所有实现已拆分到：
- profile_models.py   - 数据模型
- profile_manager.py  - 持久化与更新
- profile_narrative.py - LLM 叙事生成
- profile_extractor.py - 启动时数据提取
"""

from huaqi_src.core.profile_models import (
    UserIdentity,
    UserPreferences,
    UserBackground,
    UserProfile,
)
from huaqi_src.core.profile_manager import (
    UserProfileManager,
    get_profile_manager,
    init_profile_manager,
)
from huaqi_src.core.profile_narrative import (
    ProfileNarrative,
    ProfileNarrativeManager,
    get_narrative_manager,
    NARRATIVE_PROMPT,
)
from huaqi_src.core.profile_extractor import (
    UserDataExtractor,
    get_data_extractor,
    init_data_extractor,
    extract_user_info_on_startup,
)

__all__ = [
    # 数据模型
    "UserIdentity",
    "UserPreferences",
    "UserBackground",
    "UserProfile",
    # 管理器
    "UserProfileManager",
    "get_profile_manager",
    "init_profile_manager",
    # 叙事生成
    "ProfileNarrative",
    "ProfileNarrativeManager",
    "get_narrative_manager",
    "NARRATIVE_PROMPT",
    # 数据提取
    "UserDataExtractor",
    "get_data_extractor",
    "init_data_extractor",
    "extract_user_info_on_startup",
]
