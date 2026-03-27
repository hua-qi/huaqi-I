"""统一路径配置

支持用户自定义数据存储目录
"""

import os
from pathlib import Path


# 全局配置：用户指定的数据目录
_USER_DATA_DIR: Path = None


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
    3. ~/.huaqi/ (默认)
    """
    global _USER_DATA_DIR
    
    if _USER_DATA_DIR is not None:
        return _USER_DATA_DIR
    
    if env_dir := os.getenv("HUAQI_DATA_DIR"):
        return Path(env_dir).expanduser().resolve()
    
    return Path.home() / ".huaqi"


def get_memory_dir() -> Path:
    """获取记忆目录"""
    return get_data_dir() / "memory"


def get_drafts_dir() -> Path:
    """获取草稿目录"""
    return get_data_dir() / "drafts"


def get_vector_db_dir() -> Path:
    """获取向量数据库目录"""
    return get_data_dir() / "vector_db"


def get_models_cache_dir() -> Path:
    """获取模型缓存目录"""
    return get_data_dir() / "models"


def get_pending_reviews_dir() -> Path:
    """获取待审核目录"""
    return get_data_dir() / "pending_reviews"


def get_scheduler_db_path() -> Path:
    """获取调度器数据库路径"""
    return get_data_dir() / "scheduler.db"


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
