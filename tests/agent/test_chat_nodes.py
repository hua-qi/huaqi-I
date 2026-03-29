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
