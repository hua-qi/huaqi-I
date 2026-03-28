"""统一路径配置

支持用户自定义数据存储目录
"""

import os
from pathlib import Path
from typing import Optional


# 全局配置：用户指定的数据目录
_USER_DATA_DIR: Optional[Path] = None


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


def get_data_dir() -> Path:
    """获取数据目录
    
    优先级:
    1. 用户通过 set_data_dir() 设置的目录
    2. HUAQI_DATA_DIR 环境变量
    
    如果以上都没有设置，返回 None，由调用者处理错误
    """
    global _USER_DATA_DIR
    
    if _USER_DATA_DIR is not None:
        return _USER_DATA_DIR
    
    if env_dir := os.getenv("HUAQI_DATA_DIR"):
        return Path(env_dir).expanduser().resolve()
    
    # 返回 None 表示未配置，由调用者处理
    return None


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
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
