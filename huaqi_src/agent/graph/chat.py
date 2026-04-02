"""Chat Workflow - 对话工作流

使用 LangGraph StateGraph 构建的对话流程
"""

from pathlib import Path
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from ..state import AgentState, INTENT_CHAT, INTENT_DIARY, INTENT_SKILL, INTENT_UNKNOWN
from ..tools import (
    search_diary_tool,
    search_events_tool,
    search_work_docs_tool,
    search_worldnews_tool,
    search_person_tool,
    get_relationship_map_tool,
    search_cli_chats_tool,
    search_huaqi_chats_tool,
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
    mark_lesson_complete_tool,
)
from ..nodes.chat_nodes import (
    classify_intent,
    build_context,
    retrieve_memories,
    extract_user_info,
    generate_response,
    save_conversation,
    handle_error,
)
from ..nodes.interrupt_nodes import require_user_confirmation


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
    workflow.add_node("memory_retriever", retrieve_memories)
    workflow.add_node("extract_user_info", extract_user_info)
    workflow.add_node("chat_response", generate_response)
    
    # 交互节点
    workflow.add_node("require_user_confirmation", require_user_confirmation)
    
    # 1. 定义工具节点
    tools = [
        search_diary_tool,
        search_events_tool,
        search_work_docs_tool,
        search_worldnews_tool,
        search_person_tool,
        get_relationship_map_tool,
        search_cli_chats_tool,
        search_huaqi_chats_tool,
        get_learning_progress_tool,
        get_course_outline_tool,
        start_lesson_tool,
        mark_lesson_complete_tool,
    ]
    tool_node = ToolNode(tools)
    workflow.add_node("tools", tool_node)
    
    workflow.add_node("save_conversation", save_conversation)
    workflow.add_node("error_handler", handle_error)
    
    # 设置入口点
    workflow.set_entry_point("intent_classifier")
    
    # 条件路由: 根据意图选择分支
    def route_by_intent(state: AgentState) -> str:
        return "chat"
    
    workflow.add_conditional_edges(
        "intent_classifier",
        route_by_intent,
        {
            "chat": "context_builder",
        }
    )
    
    # 对话流程
    workflow.add_edge("context_builder", "memory_retriever")
    workflow.add_edge("memory_retriever", "chat_response")
    
    def route_by_interrupt(state: AgentState) -> str:
        if state.get("interrupt_requested"):
            return "require_user_confirmation"
        return "save_conversation"

    # 条件路由：如果有 tool call 则进入 tools 节点，否则继续原流程
    workflow.add_conditional_edges(
        "chat_response",
        tools_condition,
        {
            "tools": "tools",
            "__end__": "extract_user_info"
        }
    )
    
    # 工具执行完毕后，回到生成节点重新思考
    workflow.add_edge("tools", "chat_response")
    
    workflow.add_conditional_edges(
        "extract_user_info",
        route_by_interrupt,
        {
            "require_user_confirmation": "require_user_confirmation",
            "save_conversation": "save_conversation"
        }
    )
    
    workflow.add_edge("require_user_confirmation", "save_conversation")
    workflow.add_edge("save_conversation", END)
    
    return workflow


def compile_chat_graph(checkpoints_db_path: Path = None):
    """编译对话工作流
    
    Returns:
        可执行的 CompiledGraph
    """
    workflow = build_chat_graph()
    
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        if checkpoints_db_path is None:
            from ...config.paths import require_data_dir
            checkpoints_db_path = require_data_dir() / "checkpoints.db"
        checkpoints_db_path.parent.mkdir(parents=True, exist_ok=True)
        checkpointer = AsyncSqliteSaver.from_conn_string(str(checkpoints_db_path))
    except ImportError:
        from langgraph.checkpoint.memory import MemorySaver
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
    """运行对话（非流式，供内部测试使用）"""
    from langchain_core.messages import HumanMessage
    from ..state import create_initial_state
    
    graph = get_chat_graph()
    
    initial_state = create_initial_state(
        user_id=user_id,
        personality_context=personality_context,
    )
    initial_state["messages"] = [HumanMessage(content=message)]
    
    config = {"configurable": {"thread_id": thread_id or "default"}}
    
    result = await graph.ainvoke(initial_state, config=config)
    
    return {
        "response": result.get("response", ""),
        "intent": result.get("intent"),
        "memories": result.get("recent_memories", []),
    }
