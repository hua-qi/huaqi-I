"""统一路径配置

支持用户自定义数据存储目录
"""

import os
from pathlib import Path
from typing import Optional


# 全局配置：用户指定的数据目录
_USER_DATA_DIR: Optional[Path] = None


def _get_global_config_path() -> Path:
    """获取全局配置文件路径（用于保存数据目录等全局设置）"""
    config_dir = Path.home() / ".huaqi"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.yaml"


def _load_data_dir_from_config() -> Optional[Path]:
    """从全局配置文件读取数据目录"""
    config_path = _get_global_config_path()
    
    if config_path.exists():
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "data_dir" in data and data["data_dir"]:
                    path = Path(data["data_dir"]).expanduser().resolve()
                    if path.exists():
                        return path
        except Exception:
            pass
    
    return None


def set_data_dir(path: Path) -> Path:
    """设置用户数据目录
    
    Args:
        path: 新的数据目录路径
        
    Returns:
        设置后的数据目录
    """
    global _USER_DATA_DIR
    path = Path(path).expanduser().resolve()
    _USER_DATA_DIR = path
    
    # 确保目录存在
    ensure_dirs()
    
    return _USER_DATA_DIR


def get_data_dir() -> Optional[Path]:
    """获取数据目录
    
    优先级:
    1. 用户通过 set_data_dir() 设置的目录
    2. HUAQI_DATA_DIR 环境变量
    3. 配置文件中保存的数据目录
    
    如果以上都没有设置，返回 None，由调用者处理错误
    """
    global _USER_DATA_DIR
    
    if _USER_DATA_DIR is not None:
        return _USER_DATA_DIR
    
    if env_dir := os.getenv("HUAQI_DATA_DIR"):
        return Path(env_dir).expanduser().resolve()
    
    # 3. 从配置文件读取
    config_dir = _load_data_dir_from_config()
    if config_dir is not None:
        _USER_DATA_DIR = config_dir  # 缓存结果
        return config_dir
    
    # 返回 None 表示未配置，由调用者处理
    return None


def save_data_dir_to_config(data_dir: Path) -> bool:
    """保存数据目录到全局配置文件
    
    Args:
        data_dir: 数据目录路径
        
    Returns:
        是否成功保存
    """
    try:
        import yaml
        
        config_path = _get_global_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 读取现有配置或创建新的
        config_data = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        
        # 更新数据目录
        config_data["data_dir"] = str(data_dir.expanduser().resolve())
        
        # 保存到全局配置
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
        
        return True
    except Exception:
        return False


def require_data_dir() -> Path:
    """必须获取数据目录，如果未设置则抛出异常
    
    Raises:
        RuntimeError: 如果数据目录未设置
    """
    data_dir = get_data_dir()
    if data_dir is None:
        raise RuntimeError(
            "未设置数据目录。请使用以下方式之一指定: "
            "1. 命令行: huaqi --data-dir /path/to/data "
            "2. 环境变量: export HUAQI_DATA_DIR=/path/to/data "
            "3. 简写: huaqi -d /path/to/data"
        )
    return data_dir


def is_data_dir_set() -> bool:
    """检查数据目录是否已设置"""
    return get_data_dir() is not None


def get_memory_dir() -> Path:
    """获取记忆目录"""
    return require_data_dir() / "memory"


def get_drafts_dir() -> Path:
    """获取草稿目录"""
    return require_data_dir() / "drafts"


def get_vector_db_dir() -> Path:
    """获取向量数据库目录"""
    return require_data_dir() / "vector_db"


def get_models_cache_dir() -> Path:
    """获取模型缓存目录"""
    return require_data_dir() / "models"


def get_pending_reviews_dir() -> Path:
    """获取待审核目录"""
    return require_data_dir() / "pending_reviews"


def get_learning_dir() -> Path:
    """获取学习数据目录"""
    return require_data_dir() / "learning"


def get_diary_dir() -> Path:
    """获取日记目录"""
    return get_memory_dir() / "diary"


def get_conversations_dir() -> Path:
    """获取对话记录目录"""
    return get_memory_dir() / "conversations"


def get_work_docs_dir() -> Path:
    """获取工作文档存储目录"""
    return get_memory_dir() / "work_docs"


def get_cli_chats_dir() -> Path:
    """获取 CLI 对话记录目录"""
    return get_memory_dir() / "cli_chats"


def get_wechat_dir() -> Path:
    """获取微信聊天记录目录"""
    return get_memory_dir() / "wechat"


def get_inbox_work_docs_dir() -> Path:
    """获取待导入工作文档目录"""
    return require_data_dir() / "inbox" / "work_docs"


def get_wechat_db_dir() -> Path:
    """获取微信数据库目录"""
    return require_data_dir() / "wechat_db"


def get_people_dir() -> Path:
    """获取关系人信息目录"""
    return require_data_dir() / "people"


def get_world_dir() -> Path:
    """获取世界新闻存储目录"""
    return require_data_dir() / "world"


def get_scheduler_db_path() -> Path:
    """获取调度器数据库路径"""
    return require_data_dir() / "scheduler.db"


def ensure_dirs():
    """确保所有目录存在"""
    dirs = [
        get_memory_dir(),
        get_drafts_dir(),
        get_vector_db_dir(),
        get_models_cache_dir(),
        get_pending_reviews_dir(),
        get_learning_dir(),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
