"""LangGraph Agent State 定义

所有 workflow 共享的基础状态定义
"""

from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """LangGraph 基础状态定义

    所有 workflow 都继承这个基础状态
    """

    messages: Annotated[List[BaseMessage], add_messages]

    user_id: str

    telos_snapshot: Optional[str]           # Part2: TELOS INDEX.md 摘要（成长层快照）
    relevant_history: Optional[List[str]]   # Part3: ChromaDB 语义检索结果片段
    interaction_mode: Optional[str]         # Part4: 当前对话模式（chat/distill/report/onboarding）

    intent: Optional[str]
    intent_confidence: float

    workflow_data: Dict[str, Any]

    interrupt_requested: bool
    interrupt_reason: Optional[str]
    interrupt_data: Optional[Dict[str, Any]]

    error: Optional[str]
    retry_count: int

    response: Optional[str]


class ContentPipelineState(AgentState):
    """内容流水线专用状态"""

    source_contents: Optional[List[Dict[str, Any]]]
    selected_content: Optional[Dict[str, Any]]
    summary: Optional[str]

    generated_posts: Optional[Dict[str, str]]
    user_modified_posts: Optional[Dict[str, str]]

    publish_results: Optional[List[Dict[str, Any]]]


class DiaryWorkflowState(AgentState):
    """日记工作流状态"""

    diary_date: Optional[str]
    diary_content: Optional[str]
    diary_mood: Optional[str]
    diary_tags: Optional[List[str]]

    extracted_insights: Optional[Dict[str, Any]]
    telos_updates: Optional[Dict[str, Any]]


class InsightWorkflowState(AgentState):
    """洞察分析工作流状态"""

    analysis_type: Optional[str]
    target_data: Optional[Dict[str, Any]]
    analysis_result: Optional[Dict[str, Any]]
    requires_confirmation: bool


INTENT_CHAT = "chat"
INTENT_DIARY = "diary"
INTENT_CONTENT = "content"
INTENT_SKILL = "skill"
INTENT_UNKNOWN = "unknown"

INTENTS = [INTENT_CHAT, INTENT_DIARY, INTENT_CONTENT, INTENT_SKILL]

INTERACTION_MODE_CHAT = "chat"
INTERACTION_MODE_DISTILL = "distill"
INTERACTION_MODE_REPORT = "report"
INTERACTION_MODE_ONBOARDING = "onboarding"


def create_initial_state(
    user_id: str = "default",
    telos_snapshot: Optional[str] = None,
    relevant_history: Optional[List[str]] = None,
    interaction_mode: str = INTERACTION_MODE_CHAT,
) -> AgentState:
    return {
        "messages": [],
        "user_id": user_id,
        "telos_snapshot": telos_snapshot,
        "relevant_history": relevant_history or [],
        "interaction_mode": interaction_mode,
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
