#!/usr/bin/env python3
"""Huaqi CLI 入口

Usage:
    huaqi              # 进入交互式对话
    huaqi status       # 查看系统状态
    huaqi config       # 配置管理
"""

import atexit
import sys
import warnings
from pathlib import Path

# Python 3.14: asyncio.iscoroutinefunction 已废弃，langchain_core 仍在调用，
# 在 import 之前 patch 掉避免 DeprecationWarning 刷屏。
import asyncio
import inspect
asyncio.iscoroutinefunction = inspect.iscoroutinefunction

sys.path.insert(0, str(Path(__file__).parent))

from huaqi_src.cli import app

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)


def _quiet_shutdown():
    """退出前屏蔽所有 warning，防止 GC 回收 C 扩展连接时报刷屏。"""
    warnings.resetwarnings()
    warnings.simplefilter("ignore")


atexit.register(_quiet_shutdown)

if __name__ == "__main__":
    app()
