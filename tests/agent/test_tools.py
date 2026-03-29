import pytest
from huaqi_src.agent.tools import search_diary_tool

def test_search_diary_tool_returns_string():
    # 模拟查询一个不存在的词
    result = search_diary_tool.invoke({"query": "kaleido_test_not_exist"})
    assert isinstance(result, str)
    assert "未找到" in result
