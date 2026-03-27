"""Chat Workflow - 对话工作流

使用 LangGraph StateGraph 构建的对话流程
"""

from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..state import AgentState, INTENT_CHAT, INTENT_DIARY, INTENT_SKILL, INTENT_UNKNOWN
from ..nodes.chat_nodes import (
    classify_intent,
    build_context,
    retrieve_memories,
    generate_response,
    save_conversation,
    handle_error,
)


def build_chat_graph() -> StateGraph:
    """构建对话 workflow 图
    
    流程:
    1. intent_classifier -> 识别意图
    2. 根据意图路由到不同分支
       - chat: 进入对话流程
       - diary: 日记处理 (暂不支持)
       - skill: 技能处理 (暂不支持)
    3. context_builder -> 构建上下文
    4. memory_retriever -> 检索记忆
    5. chat_response -> 生成回复
    6. save_conversation -> 保存对话
    
    Returns:
        编译后的 StateGraph
    """
    
    # 创建工作流
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("intent_classifier", classify_intent)
    workflow.add_node("context_builder", build_context)
    workflow.add_node("chat_response", generate_response)
    workflow.add_node("save_conversation", save_conversation)
    workflow.add_node("error_handler", handle_error)
    
    # 设置入口点
    workflow.set_entry_point("intent_classifier")
    
    # 条件路由: 根据意图选择分支
    def route_by_intent(state: AgentState) -> str:
        intent = state.get("intent", INTENT_CHAT)
        
        # 暂时只支持 chat 意图，其他都路由到 chat
        # 后续可以实现 diary 和 skill 的专门处理
        if intent == INTENT_DIARY:
            return "chat"  # 暂用 chat 处理
        elif intent == INTENT_SKILL:
            return "chat"  # 暂用 chat 处理
        else:
            return "chat"
    
    workflow.add_conditional_edges(
        "intent_classifier",
        route_by_intent,
        {
            "chat": "context_builder",
        }
    )
    
    # 对话流程
    workflow.add_edge("context_builder", "chat_response")
    workflow.add_edge("chat_response", "save_conversation")
    workflow.add_edge("save_conversation", END)
    
    # 错误处理 (可以从任何节点转到 error_handler)
    # 这里简化处理，在 generate_response 中处理错误
    
    return workflow


def compile_chat_graph():
    """编译对话工作流
    
    Returns:
        可执行的 CompiledGraph
    """
    workflow = build_chat_graph()
    
    # 使用内存 checkpoint (后续可改为持久化)
    checkpointer = MemorySaver()
    
    compiled = workflow.compile(checkpointer=checkpointer)
    return compiled


# 单例
_compiled_graph = None


def get_chat_graph():
    """获取编译后的 chat graph 单例"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = compile_chat_graph()
    return _compiled_graph


async def run_chat(
    message: str,
    user_id: str = "default",
    personality_context: str = None,
    thread_id: str = None,
) -> Dict[str, Any]:
    """运行对话
    
    Args:
        message: 用户消息
        user_id: 用户ID
        personality_context: 人格画像上下文
        thread_id: 对话线程ID
        
    Returns:
        包含回复和状态的结果
    """
    from langchain_core.messages import HumanMessage
    from ..state import create_initial_state
    
    # 获取图
    graph = get_chat_graph()
    
    # 创建初始状态
    initial_state = create_initial_state(
        user_id=user_id,
        personality_context=personality_context,
    )
    
    # 添加用户消息
    initial_state["messages"] = [HumanMessage(content=message)]
    
    # 配置 (包含 thread_id 用于持久化)
    config = {"configurable": {"thread_id": thread_id or "default"}}
    
    # 执行
    result = await graph.ainvoke(initial_state, config=config)
    
    return {
        "response": result.get("response", ""),
        "intent": result.get("intent"),
        "memories": result.get("recent_memories", []),
    }
