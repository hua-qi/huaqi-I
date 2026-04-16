#!/usr/bin/env python3
"""
Key Code Examples from Codeflicker Tool Calling Research
========================================================

This file contains the critical code patterns for implementing tool calling
with LangChain + LangGraph, based on analysis of huaqi-growing project.
"""

# ============================================================================
# 1. TOOL DEFINITION AND REGISTRATION
# ============================================================================
# File: huaqi_src/agent/tools.py

from langchain_core.tools import tool

# Tool registry - list of all available tools
_TOOL_REGISTRY: list = []

def register_tool(fn):
    """Decorator to register a tool in the global registry"""
    _TOOL_REGISTRY.append(fn)
    return fn

# Example tool definition
@register_tool
@tool
def search_diary_tool(query: str) -> str:
    """搜索用户的历史日记内容。
    
    当用户询问过去发生的事情、特定的回忆或关键词时使用。
    
    Args:
        query: 搜索关键词
        
    Returns:
        搜索结果或"未找到"消息
    """
    from huaqi_src.layers.data.diary import DiaryStore
    from huaqi_src.config.paths import get_memory_dir
    
    store = DiaryStore(get_memory_dir())
    results = store.search(query)
    
    if not results:
        return f"未找到包含 '{query}' 的相关日记。"
    
    formatted_results = [f"日期: {r.date}\n内容: {r.content}" for r in results[:3]]
    return "找到以下日记记录：\n\n" + "\n---\n".join(formatted_results)


@register_tool
@tool
def google_search_tool(query: str) -> str:
    """在互联网上搜索最新信息、新闻、热点事件。
    
    当用户询问近期新闻、实时动态、或本地数据库无法回答的时事问题时使用。
    """
    import time
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    
    last_err = None
    for attempt in range(3):
        try:
            if attempt > 0:
                time.sleep(3 * attempt)
            with DDGS(timeout=20) as ddgs:
                results = list(ddgs.text(query, max_results=5))
            if not results:
                return f"未找到关于 '{query}' 的相关信息"
            lines = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                lines.append(f"【{title}】\n{body}\n{href}")
            return "\n\n".join(lines)
        except Exception as e:
            last_err = e
            # Handle rate limits and timeouts
            msg = str(e).lower()
            if "ratelimit" in msg or "timeout" in msg:
                continue
            break
    
    # Fallback error message
    msg = str(last_err).lower()
    if "timeout" in msg:
        return "网络搜索暂时不可用，请稍后重试"
    if "ratelimit" in msg:
        return "搜索频率过高，请稍后再试"
    return f"搜索失败: {str(last_err)[:80]}"


# ============================================================================
# 2. SYSTEM PROMPT WITH TOOL USAGE GUIDANCE
# ============================================================================
# File: huaqi_src/agent/nodes/chat_nodes.py

def build_system_prompt(
    personality_context: str = None,
    user_profile_context: str = None,
) -> str:
    """构建系统提示词，指导 LLM 如何使用工具"""
    
    base_prompt = """你是 Huaqi (花旗)，一个个人 AI 伴侣系统。

你的职责：
1. 作为用户的数字伙伴，提供陪伴和支持
2. 记住用户的重要信息和偏好
3. 帮助用户记录日记、追踪成长、管理目标
4. 在内容创作时提供协助
5. ★ 当用户询问新闻、时事、世界动态时，必须先调用 search_worldnews_tool 查询本地数据；
     如果工具返回"本地未找到"或无结果，必须紧接着调用 google_search_tool 在互联网上搜索，
     不得直接回答 ★

回复风格：
- 温暖、真诚、有同理心
- 简洁明了，避免冗长
- 适当使用 emoji 增加亲和力
- 记住用户的上下文，保持对话连贯
- 根据用户的情绪状态调整回应方式
- 关注用户的深层需求，不只是表面问题
"""
    
    if personality_context:
        base_prompt += f"\n\n{personality_context}\n"
    
    if user_profile_context:
        base_prompt += f"\n{user_profile_context}\n"
    
    return base_prompt


# ============================================================================
# 3. LLM BINDING WITH TOOLS (THE CRITICAL PART)
# ============================================================================
# File: huaqi_src/agent/nodes/chat_nodes.py

async def generate_response(state, config=None):
    """生成回复节点 - 调用 LLM 并绑定工具"""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage
    
    messages = state.get("messages", [])
    workflow_data = state.get("workflow_data", {})
    memories = state.get("recent_memories", [])
    
    # Step 1: 构建完整的系统提示词
    system_prompt = workflow_data.get("system_prompt", build_system_prompt())
    
    if memories:
        trimmed = [m[:200] for m in memories]
        combined = "\n".join([f"- {m}" for m in trimmed])
        if len(combined) > 1000:
            combined = combined[:1000] + "\n...(记忆截断)"
        system_prompt += f"\n\n相关历史记忆（自动检索）：\n{combined}"
    
    full_messages = [SystemMessage(content=system_prompt)] + messages
    
    # Step 2: 创建聊天模型
    chat_model = ChatOpenAI(
        model="gpt-4",  # 或其他模型
        api_key="your-api-key",
        temperature=1,
        max_tokens=1500,
        streaming=True,
    )
    
    # ★★★ STEP 3: 绑定工具 - 这是魔法所在 ★★★
    # chat_model.bind_tools() 自动：
    # 1. 为每个工具生成 JSON Schema
    # 2. 将 tools 数组注入到 API 参数中
    # 3. 返回包装过的模型，当调用时支持 tool_calls
    from ..tools import _TOOL_REGISTRY
    chat_model_with_tools = chat_model.bind_tools(_TOOL_REGISTRY)
    
    # Step 4: 流式调用模型
    # 模型会自动决定是否需要调用工具
    response_msg = None
    async for chunk in chat_model_with_tools.astream(full_messages, config=config):
        if response_msg is None:
            response_msg = chunk
        else:
            response_msg += chunk
    
    # Step 5: 返回响应
    # response_msg.tool_calls 会自动包含在内（如果 LLM 决定调用工具）
    return {
        "response": response_msg.content,
        "messages": [response_msg],
    }


# ============================================================================
# 4. LANGGRAPH WORKFLOW WITH TOOL CALLING
# ============================================================================
# File: huaqi_src/agent/graph/chat.py

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

def build_chat_graph():
    """构建包含工具调用的对话工作流"""
    workflow = StateGraph(AgentState)
    
    # Step 1: 添加所有节点
    workflow.add_node("intent_classifier", classify_intent)
    workflow.add_node("context_builder", build_context)
    workflow.add_node("memory_retriever", retrieve_memories)
    workflow.add_node("chat_response", generate_response)  # ← LLM 节点
    workflow.add_node("extract_user_info", extract_user_info)
    
    # Step 2: 创建工具节点
    # ToolNode 是 LangGraph 的预构建节点，自动处理 tool_calls 执行
    tool_node = ToolNode(_TOOL_REGISTRY)
    workflow.add_node("tools", tool_node)
    
    workflow.add_node("save_conversation", save_conversation)
    
    # Step 3: 设置入口点
    workflow.set_entry_point("intent_classifier")
    
    # Step 4: 定义流程
    def route_by_intent(state):
        return "chat"
    
    workflow.add_conditional_edges(
        "intent_classifier",
        route_by_intent,
        {"chat": "context_builder"}
    )
    
    workflow.add_edge("context_builder", "memory_retriever")
    workflow.add_edge("memory_retriever", "chat_response")
    
    # ★★★ STEP 5: 条件路由 - 工具调用的关键 ★★★
    # tools_condition 是 LangGraph 提供的内置函数
    # 它自动检查最后一条消息是否有 tool_calls
    # 如果有，路由到 "tools" 节点
    # 如果没有，路由到 "__end__" (跳过工具执行)
    workflow.add_conditional_edges(
        "chat_response",        # 从这个节点出发
        tools_condition,        # 使用这个路由函数
        {
            "tools": "tools",             # 如果有 tool_calls
            "__end__": "extract_user_info"  # 否则继续
        }
    )
    
    # Step 6: 工具执行后回到 LLM（自动循环）
    # 这形成了一个循环：
    # chat_response → (有 tool_calls) → tools → chat_response
    workflow.add_edge("tools", "chat_response")
    
    # Step 7: 其他流程
    def route_by_interrupt(state):
        if state.get("interrupt_requested"):
            return "require_user_confirmation"
        return "save_conversation"
    
    workflow.add_conditional_edges(
        "extract_user_info",
        route_by_interrupt,
        {
            "require_user_confirmation": "require_user_confirmation",
            "save_conversation": "save_conversation"
        }
    )
    
    workflow.add_edge("save_conversation", END)
    
    return workflow


# ============================================================================
# 5. WHAT HAPPENS INSIDE tools_condition AND ToolNode
# ============================================================================
# (These are LangGraph built-ins, but here's how they work)

def tools_condition(state) -> str:
    """
    自动检查消息中是否有 tool_calls
    
    Returns:
        "tools" - 有 tool_calls，继续执行工具
        "__end__" - 无 tool_calls，终止路由
    """
    messages = state.get("messages", [])
    
    if not messages:
        return "__end__"
    
    last_message = messages[-1]
    
    # 检查最后一条消息是否是 AIMessage 且有 tool_calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    else:
        return "__end__"


class ToolNodeSimulation:
    """模拟 ToolNode 的行为（实际由 LangGraph 提供）"""
    
    def __init__(self, tools_registry):
        self.tools_map = {tool.name: tool for tool in tools_registry}
    
    def __call__(self, state):
        """执行所有 tool_calls 并返回结果"""
        from langchain_core.messages import ToolMessage
        import json
        
        messages = state.get("messages", [])
        
        if not messages:
            return {"messages": messages}
        
        last_message = messages[-1]
        
        # 只处理有 tool_calls 的消息
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {"messages": messages}
        
        tool_results = []
        
        # 执行每个 tool_call
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_input = json.loads(tool_call["function"]["arguments"])
            
            # 从注册表找到工具
            if tool_name not in self.tools_map:
                tool_result = f"Error: Tool {tool_name} not found"
            else:
                tool = self.tools_map[tool_name]
                try:
                    # 执行工具
                    result = tool.invoke(tool_input)
                    tool_result = str(result)
                except Exception as e:
                    tool_result = f"Error executing {tool_name}: {str(e)}"
            
            # 创建 ToolMessage（工具执行结果）
            tool_message = ToolMessage(
                content=tool_result,
                tool_call_id=tool_call["id"],
                name=tool_name
            )
            tool_results.append(tool_message)
        
        # 将工具结果注入消息列表
        new_messages = messages + tool_results
        return {"messages": new_messages}


# ============================================================================
# 6. MESSAGE EVOLUTION EXAMPLE
# ============================================================================
"""
Complete example of how messages evolve during tool calling:

Initial State:
  messages = [
    SystemMessage(content="你是 Huaqi...必须调用工具..."),
    HumanMessage(content="查询日记中的 kaleido")
  ]

After chat_response node:
  messages = [
    SystemMessage(...),
    HumanMessage(...),
    AIMessage(
      content=None,
      tool_calls=[
        {
          "id": "call_abc123",
          "type": "function",
          "function": {
            "name": "search_diary_tool",
            "arguments": '{"query": "kaleido"}'
          }
        }
      ]
    )
  ]

After tools_condition check:
  Returns "tools" → route to tools node

After ToolNode execution:
  messages = [
    SystemMessage(...),
    HumanMessage(...),
    AIMessage(tool_calls=[...]),
    ToolMessage(
      content="找到以下日记记录：\n日期: 2026-01-15\n内容: kaleido 项目架构设计...",
      tool_call_id="call_abc123",
      name="search_diary_tool"
    )
  ]

After tools_condition check (second time):
  last_message is ToolMessage (no tool_calls)
  Returns "__end__" → proceed to extract_user_info

Next execution can see complete history:
  - All tool calls and their results
  - Complete conversation context
  - Can generate final response based on all information
"""


# ============================================================================
# 7. MINIMAL WORKING EXAMPLE
# ============================================================================

def minimal_example():
    """Minimal complete example of tool calling"""
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode, tools_condition
    
    # Define a tool
    @tool
    def my_search_tool(query: str) -> str:
        """Search database for information."""
        return f"Found results for: {query}"
    
    tools = [my_search_tool]
    
    # Create LLM
    llm = ChatOpenAI(model="gpt-4")
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Define node
    def call_llm(state):
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}
    
    # Build graph
    graph = StateGraph({"messages": list})
    graph.add_node("llm", call_llm)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge("START", "llm")
    
    # Conditional edges - THE KEY
    graph.add_conditional_edges(
        "llm",
        tools_condition,
        {"tools": "tools", "__end__": END}
    )
    
    # Loop back
    graph.add_edge("tools", "llm")
    
    # Compile and run
    compiled = graph.compile()
    
    result = compiled.invoke({
        "messages": [HumanMessage(content="search for information")]
    })
    
    return result


if __name__ == "__main__":
    print(__doc__)
    print("\nKey code examples saved.")
    print("\nMain concepts:")
    print("1. Tool definition with @register_tool decorator")
    print("2. System prompt with tool usage guidance")
    print("3. chat_model.bind_tools() - the critical binding")
    print("4. StateGraph with ToolNode and tools_condition")
    print("5. Automatic message injection and loop management")
