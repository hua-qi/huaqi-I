# Agentic Memory Retrieval Implementation Plan

**Goal:** 允许 Agent 通过 Tool Calling 自主路由并检索包括日记在内的所有时间段的多维用户数据，解决基于正则的僵化意图识别导致的“记忆断层”问题。

**Architecture:** 采用 LangGraph 的 ToolNode 范式。废弃基于正则的 `classify_intent`，将 `search_diary_tool` 等工具绑定到 LLM 节点。LLM 根据用户问题（如“你知道 kaleido 吗”）自主决定触发检索工具，图（Graph）条件路由至 ToolNode 执行本地 Markdown 搜索后，再返回 LLM 生成最终回答。

**Tech Stack:** Python 3, LangChain, LangGraph, pytest

---

### Task 1: 编写检索工具 (Retrieval Tools)

**Files:**
- Create: `huaqi_src/agent/tools.py`
- Create: `tests/agent/test_tools.py`

**Step 1: Write the failing test**

```python
# tests/agent/test_tools.py
import pytest
from huaqi_src.agent.tools import search_diary_tool

def test_search_diary_tool_returns_string():
    # 模拟查询一个不存在的词
    result = search_diary_tool.invoke({"query": "kaleido_test_not_exist"})
    assert isinstance(result, str)
    assert "未找到" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_tools.py::test_search_diary_tool_returns_string -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'huaqi_src.agent.tools'"

**Step 3: Write minimal implementation**

```python
# huaqi_src/agent/tools.py
from langchain_core.tools import tool
from huaqi_src.core.diary_simple import DiaryStore
from huaqi_src.core.config_paths import get_memory_dir

@tool
def search_diary_tool(query: str) -> str:
    """搜索用户的历史日记内容。当用户询问过去发生的事情、特定的回忆或关键词（如kaleido）时使用。"""
    store = DiaryStore(get_memory_dir())
    results = store.search(query)
    
    if not results:
        return f"未找到包含 '{query}' 的相关日记。"
        
    formatted_results = [f"日期: {r.date}\n内容: {r.content}" for r in results[:3]]
    return "找到以下日记记录：\n\n" + "\n---\n".join(formatted_results)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_tools.py::test_search_diary_tool_returns_string -v`
Expected: PASS

**Step 5: Commit**
Run: `git add huaqi_src/agent/tools.py tests/agent/test_tools.py && git commit -m "feat: add search_diary_tool for agentic retrieval"`

---

### Task 2: 将工具绑定到 LLM 节点

**Files:**
- Modify: `huaqi_src/agent/nodes/chat_nodes.py`
- Create: `tests/agent/test_chat_nodes.py`

**Step 1: Write the failing test**

```python
# tests/agent/test_chat_nodes.py
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_chat_nodes.py::test_generate_response_binds_tools -v`
Expected: FAIL with assertion error (tool_calls missing or empty)

**Step 3: Write minimal implementation**

Modify `huaqi_src/agent/nodes/chat_nodes.py` 中的 `generate_response` 函数。在初始化 `chat_model` 后，绑定工具：

```python
# huaqi_src/agent/nodes/chat_nodes.py (在 chat_model 实例化后添加)
        from langchain_openai import ChatOpenAI
        from ..tools import search_diary_tool
        
        chat_model = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=1,
            max_tokens=cfg.max_tokens,
            streaming=True,
        )
        
        # 绑定工具
        tools = [search_diary_tool]
        chat_model_with_tools = chat_model.bind_tools(tools)
        
        response_content = ""
        # 替换原有的 chat_model.astream 为 chat_model_with_tools.astream
        async for chunk in chat_model_with_tools.astream(full_messages, config=config):
            if chunk.content:
                response_content += chunk.content
            # 需要保留 tool_call chunks
            
        # 注意：由于涉及 tool_calls，流式处理需要额外处理 chunk.tool_call_chunks
        # 为了极简，这里改用 ainvoke 获取完整结果（如果涉及 tool calling，通常由 langgraph 自动处理）
        ai_msg = await chat_model_with_tools.ainvoke(full_messages, config=config)
        
        return {
            "response": ai_msg.content,
            "messages": [ai_msg],
        }
```
*(注意：在实际代码中，需要妥善处理原有逻辑中的纯文本 Streaming 与 Tool Calling Chunk 的合并，这里给出最简的 `ainvoke` 替换方案以通过测试)*

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_chat_nodes.py::test_generate_response_binds_tools -v`
Expected: PASS

**Step 5: Commit**
Run: `git add huaqi_src/agent/nodes/chat_nodes.py tests/agent/test_chat_nodes.py && git commit -m "feat: bind tools to llm node"`

---

### Task 3: 重构 LangGraph 路由 (引入 ToolNode)

**Files:**
- Modify: `huaqi_src/agent/graph/chat.py`
- Create: `tests/agent/test_graph.py`

**Step 1: Write the failing test**

```python
# tests/agent/test_graph.py
import pytest
from langgraph.graph import StateGraph
from huaqi_src.agent.graph.chat import build_chat_graph
from langchain_core.messages import HumanMessage

def test_graph_has_tools_node():
    graph = build_chat_graph()
    # 编译后的图中应该包含 'tools' 节点
    assert "tools" in graph.nodes
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_graph.py::test_graph_has_tools_node -v`
Expected: FAIL with "AssertionError: assert 'tools' in {...}"

**Step 3: Write minimal implementation**

Modify `huaqi_src/agent/graph/chat.py` 引入 ToolNode 并设置条件路由：

```python
# huaqi_src/agent/graph/chat.py
from langgraph.prebuilt import ToolNode, tools_condition
from ..tools import search_diary_tool

# 在 build_chat_graph 函数中添加：
def build_chat_graph():
    # ... 原有节点定义 ...
    
    # 1. 定义工具节点
    tools = [search_diary_tool]
    tool_node = ToolNode(tools)
    workflow.add_node("tools", tool_node)
    
    # 2. 修改路由逻辑
    # 移除原有的固定路由，改为条件路由
    workflow.add_conditional_edges(
        "generate_response",  # 假设原来的生成节点叫这个
        tools_condition,
        {
            "tools": "tools",
            "__end__": "__end__"
        }
    )
    
    # 3. 工具执行完毕后，回到生成节点重新思考
    workflow.add_edge("tools", "generate_response")
    
    # ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_graph.py::test_graph_has_tools_node -v`
Expected: PASS

**Step 5: Commit**
Run: `git add huaqi_src/agent/graph/chat.py tests/agent/test_graph.py && git commit -m "feat: integrate tool node into langgraph workflow"`
