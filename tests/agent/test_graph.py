import pytest
from langgraph.graph import StateGraph
from huaqi_src.agent.graph.chat import build_chat_graph
from langchain_core.messages import HumanMessage

def test_graph_has_tools_node():
    graph = build_chat_graph()
    # 编译后的图中应该包含 'tools' 节点
    assert "tools" in graph.nodes
