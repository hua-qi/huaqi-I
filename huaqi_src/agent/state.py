"""LangGraph Agent State 定义

所有 workflow 共享的基础状态定义
"""

from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class AgentState(TypedDict):
    """LangGraph 基础状态定义
    
    所有 workflow 都继承这个基础状态
    """
    
    # 基础对话历史 (使用 add_messages 自动追加)
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 用户上下文
    user_id: str
    personality_context: Optional[str]          # 人格画像 prompt 片段
    recent_memories: Optional[List[str]]        # 相关记忆片段
    
    # 意图与路由
    intent: Optional[str]                       # chat / diary / content / skill
    intent_confidence: float
    
    # 工作流特定数据（动态）
    workflow_data: Dict[str, Any]               # 各节点传递的数据
    
    # 人机协同
    interrupt_requested: bool
    interrupt_reason: Optional[str]
    interrupt_data: Optional[Dict[str, Any]]    # 等待用户处理的数据
    
    # 错误与重试
    error: Optional[str]
    retry_count: int
    
    # 输出
    response: Optional[str]                     # 最终回复内容


class ContentPipelineState(AgentState):
    """内容流水线专用状态"""
    
    # 内容源
    source_contents: Optional[List[Dict[str, Any]]]     # 抓取的内容
    selected_content: Optional[Dict[str, Any]]
    summary: Optional[str]
    
    # 生成内容
    generated_posts: Optional[Dict[str, str]]            # {platform: content}
    user_modified_posts: Optional[Dict[str, str]]        # 用户修改后的
    
    # 发布结果
    publish_results: Optional[List[Dict[str, Any]]]


class DiaryWorkflowState(AgentState):
    """日记工作流状态"""
    
    diary_date: Optional[str]
    diary_content: Optional[str]
    diary_mood: Optional[str]
    diary_tags: Optional[List[str]]
    
    extracted_insights: Optional[Dict[str, Any]]         # AI 提取的洞察
    personality_updates: Optional[Dict[str, Any]]        # 画像更新建议


class InsightWorkflowState(AgentState):
    """洞察分析工作流状态"""
    
    analysis_type: Optional[str]                          # personality_update / weekly_review
    target_data: Optional[Dict[str, Any]]                 # 要分析的数据
    analysis_result: Optional[Dict[str, Any]]             # 分析结果
    requires_confirmation: bool                           # 是否需要用户确认


# 意图定义
INTENT_CHAT = "chat"
INTENT_DIARY = "diary"
INTENT_CONTENT = "content"
INTENT_SKILL = "skill"
INTENT_UNKNOWN = "unknown"

INTENTS = [INTENT_CHAT, INTENT_DIARY, INTENT_CONTENT, INTENT_SKILL]


def create_initial_state(
    user_id: str = "default",
    personality_context: Optional[str] = None,
) -> AgentState:
    """创建初始状态
    
    Args:
        user_id: 用户ID
        personality_context: 人格画像上下文
        
    Returns:
        初始状态字典
    """
    return {
        "messages": [],
        "user_id": user_id,
        "personality_context": personality_context,
        "recent_memories": [],
        "intent": None,
        "intent_confidence": 0.0,
        "workflow_data": {},
        "interrupt_requested": False,
        "interrupt_reason": None,
        "interrupt_data": None,
        "error": None,
        "retry_count": 0,
        "response": None,
    }
