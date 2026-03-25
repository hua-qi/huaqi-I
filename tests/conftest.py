"""测试配置文件

提供测试用的 fixtures 和配置
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """创建临时目录，测试结束后自动清理"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_user_id() -> str:
    """测试用户ID"""
    return "test_user_12345"


@pytest.fixture
def sample_markdown_content() -> str:
    """示例 Markdown 内容"""
    return """---
type: identity
created_at: 2026-03-24T10:00:00
---

# 测试用户

## 基本信息

- **姓名**: 测试用户
- **职业**: 软件工程师
"""


@pytest.fixture
def sample_conversation_turns() -> list:
    """示例对话轮次"""
    return [
        {
            "user_message": "你好",
            "assistant_response": "你好！很高兴见到你。",
            "metadata": {"model": "test"}
        },
        {
            "user_message": "今天天气怎么样？",
            "assistant_response": "抱歉，我无法获取实时天气信息。",
            "metadata": {"model": "test"}
        }
    ]
