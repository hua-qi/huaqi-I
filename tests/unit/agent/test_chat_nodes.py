import pytest
from langchain_core.messages import HumanMessage
from huaqi_src.agent.nodes.chat_nodes import generate_response
import asyncio

@pytest.mark.asyncio
async def test_generate_response_binds_tools():
    state = {"messages": [HumanMessage(content="查询日记中的 kaleido")], "workflow_data": {}}
    result = await generate_response(state)
    
    # 验证 LLM 返回的消息中包含 tool_calls
    last_message = result["messages"][-1]
    assert hasattr(last_message, "tool_calls")


from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from huaqi_src.agent.state import create_initial_state


def _make_state_with_query(query: str) -> dict:
    state = create_initial_state()
    state["messages"] = [HumanMessage(content=query)]
    return state


def test_retrieve_memories_includes_today_markdown(tmp_path):
    """当天的 Markdown 对话应被检索到，即使向量库为空"""
    from huaqi_src.layers.data.memory.storage.markdown_store import MarkdownMemoryStore
    from huaqi_src.config import paths as config_paths

    config_paths._USER_DATA_DIR = tmp_path

    store = MarkdownMemoryStore(tmp_path / "memory" / "conversations")
    store.save_conversation(
        session_id="today_session",
        timestamp=datetime.now(),
        turns=[{"user_message": "我合并错了分支", "assistant_response": "回滚即可"}],
    )

    with patch("huaqi_src.layers.data.memory.vector.get_hybrid_search", side_effect=Exception("no chroma")):
        from importlib import reload
        import huaqi_src.agent.nodes.chat_nodes as nodes
        reload(nodes)
        state = _make_state_with_query("我有没有说过合并分支的事")
        result = nodes.retrieve_memories(state)

    memories = result.get("recent_memories", [])
    assert len(memories) > 0
    assert any("合并" in m for m in memories)


def test_retrieve_memories_falls_back_gracefully(tmp_path):
    """当向量库和 Markdown 都不可用时，返回空列表而不报错"""
    from huaqi_src.config import paths as config_paths
    config_paths._USER_DATA_DIR = tmp_path

    with patch("huaqi_src.layers.data.memory.vector.get_hybrid_search", side_effect=Exception("no chroma")):
        from importlib import reload
        import huaqi_src.agent.nodes.chat_nodes as nodes
        reload(nodes)
        state = _make_state_with_query("随便什么内容")
        result = nodes.retrieve_memories(state)

    assert result == {"recent_memories": []}


class TestBuildContextWithTelos:
    def test_build_context_injects_telos_snapshot(self, tmp_path):
        from huaqi_src.agent.state import create_initial_state
        from huaqi_src.agent.nodes.chat_nodes import build_context
        from huaqi_src.config import paths as config_paths
        from huaqi_src.layers.growth.telos.manager import TelosManager
        from unittest.mock import patch
        from datetime import datetime, timezone
        from huaqi_src.layers.growth.telos.models import HistoryEntry

        config_paths._USER_DATA_DIR = tmp_path
        telos_dir = tmp_path / "telos"
        telos_dir.mkdir()
        mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
        mgr.init()
        entry = HistoryEntry(
            version=1, change="测试", trigger="测试",
            confidence=0.8, updated_at=datetime.now(timezone.utc)
        )
        mgr.update("beliefs", "选择比努力更重要", entry, 0.8)

        state = create_initial_state()
        with patch("huaqi_src.agent.nodes.chat_nodes._get_telos_manager", return_value=mgr):
            result = build_context(state)

        system_prompt = result["workflow_data"]["system_prompt"]
        assert "选择比努力更重要" in system_prompt

    def test_build_context_falls_back_gracefully_when_no_telos(self, tmp_path):
        from huaqi_src.agent.state import create_initial_state
        from huaqi_src.agent.nodes.chat_nodes import build_context
        from huaqi_src.config import paths as config_paths

        config_paths._USER_DATA_DIR = tmp_path
        state = create_initial_state()
        result = build_context(state)
        assert "system_prompt" in result["workflow_data"]
