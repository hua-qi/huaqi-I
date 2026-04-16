import pytest
from huaqi_src.agent.tools import search_diary_tool

def test_search_diary_tool_returns_string():
    result = search_diary_tool.invoke({"query": "kaleido_test_not_exist"})
    assert isinstance(result, str)
    assert "未找到" in result

from huaqi_src.agent.tools import search_work_docs_tool

def test_search_work_docs_tool_returns_string_when_no_docs():
    result = search_work_docs_tool.invoke({"query": "不可能存在的内容xyz"})
    assert isinstance(result, str)
    assert "未找到" in result

from huaqi_src.agent.tools import search_person_tool, get_relationship_map_tool

def test_search_person_tool_returns_string_when_no_data():
    result = search_person_tool.invoke({"name": "不存在的人xyz"})
    assert isinstance(result, str)
    assert "未找到" in result

def test_get_relationship_map_tool_returns_string():
    result = get_relationship_map_tool.invoke({})
    assert isinstance(result, str)


def test_search_cli_chats_tool_returns_string_when_no_data(tmp_path):
    import os
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    from huaqi_src.agent.tools import search_cli_chats_tool
    result = search_cli_chats_tool.invoke({"query": "watchdog"})
    assert isinstance(result, str)


def test_search_huaqi_chats_tool_returns_string_when_no_data(tmp_path):
    import os
    from huaqi_src.config import paths as config_paths
    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    config_paths._USER_DATA_DIR = tmp_path
    from importlib import reload
    import huaqi_src.agent.tools as tools_module
    reload(tools_module)
    from huaqi_src.agent.tools import search_huaqi_chats_tool
    result = search_huaqi_chats_tool.invoke({"query": "犯错"})
    assert isinstance(result, str)
    assert "未找到" in result


def test_search_huaqi_chats_tool_finds_content(tmp_path):
    import os
    from datetime import datetime
    from huaqi_src.layers.data.memory.storage.markdown_store import MarkdownMemoryStore
    from huaqi_src.config import paths as config_paths

    os.environ["HUAQI_DATA_DIR"] = str(tmp_path)
    config_paths._USER_DATA_DIR = tmp_path

    store = MarkdownMemoryStore(tmp_path / "memory" / "conversations")
    store.save_conversation(
        session_id="test_session",
        timestamp=datetime.now(),
        turns=[{"user_message": "我犯错了", "assistant_response": "没关系的"}],
    )

    from importlib import reload
    import huaqi_src.agent.tools as tools_module
    reload(tools_module)
    from huaqi_src.agent.tools import search_huaqi_chats_tool
    result = search_huaqi_chats_tool.invoke({"query": "犯错"})
    assert isinstance(result, str)
    assert "犯错" in result or "找到" in result


from unittest.mock import patch, MagicMock

def _make_mock_ddgs(return_value=None, side_effect=None):
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    if side_effect is not None:
        mock_ddgs.text = MagicMock(side_effect=side_effect)
    else:
        mock_ddgs.text = MagicMock(return_value=iter(return_value or []))
    return mock_ddgs

def test_google_search_tool_returns_formatted_results():
    fake_results = [
        {"title": "AI 新闻", "body": "大模型发展迅速", "href": "https://example.com/1"},
        {"title": "科技动态", "body": "量子计算突破", "href": "https://example.com/2"},
    ]
    mock_ddgs = _make_mock_ddgs(return_value=fake_results)

    from huaqi_src.agent.tools import google_search_tool
    with patch("ddgs.DDGS", return_value=mock_ddgs):
        result = google_search_tool.invoke({"query": "AI 新闻"})

    assert isinstance(result, str)
    assert "AI 新闻" in result
    assert "https://example.com/1" in result


def test_google_search_tool_returns_empty_message_when_no_results():
    mock_ddgs = _make_mock_ddgs(return_value=[])

    from huaqi_src.agent.tools import google_search_tool
    with patch("ddgs.DDGS", return_value=mock_ddgs):
        result = google_search_tool.invoke({"query": "xyznotexist"})

    assert isinstance(result, str)
    assert "未找到" in result


def test_google_search_tool_handles_network_timeout():
    mock_ddgs = _make_mock_ddgs(side_effect=Exception("Connection timed out"))

    from huaqi_src.agent.tools import google_search_tool
    with patch("ddgs.DDGS", return_value=mock_ddgs):
        result = google_search_tool.invoke({"query": "test"})

    assert "暂时不可用" in result


def test_google_search_tool_handles_rate_limit():
    mock_ddgs = _make_mock_ddgs(side_effect=Exception("ratelimit exceeded"))

    from huaqi_src.agent.tools import google_search_tool
    with patch("ddgs.DDGS", return_value=mock_ddgs):
        result = google_search_tool.invoke({"query": "test"})

    assert "频率过高" in result


def test_search_person_tool_in_registry():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    tool_names = [t.name for t in _TOOL_REGISTRY if hasattr(t, "name")]
    assert "search_person_tool" in tool_names


def test_search_memory_tool_in_registry():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    tool_names = [t.name for t in _TOOL_REGISTRY if hasattr(t, "name")]
    assert "search_memory_tool" in tool_names
