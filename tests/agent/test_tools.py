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
    from huaqi_src.core import config_paths
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
    from huaqi_src.memory.storage.markdown_store import MarkdownMemoryStore
    from huaqi_src.core import config_paths

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
