#!/usr/bin/env python3
"""Huaqi CLI 入口

Usage:
    huaqi              # 进入交互式对话
    huaqi status       # 查看系统状态
    huaqi config       # 配置管理
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from huaqi_src.cli import app

if __name__ == "__main__":
    app()
