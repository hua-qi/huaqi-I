"""中断节点与恢复机制

实现 LangGraph 的 interrupt 和 resume 功能，用于人机协同。
"""

from typing import Dict, Any, Optional
from langgraph.types import interrupt

from ..state import AgentState

def require_user_confirmation(state: AgentState) -> AgentState:
    """需要用户确认的节点
    
    使用 LangGraph 原生的 interrupt 暂停执行，等待外部输入
    """
    if state.get("interrupt_requested"):
        # 抛出中断，等待用户恢复
        user_response = interrupt({
            "reason": state.get("interrupt_reason", "需要用户确认"),
            "data": state.get("interrupt_data", {})
        })
        
        # 恢复后，将用户的输入保存到状态中
        state["workflow_data"]["user_confirmation"] = user_response
        state["interrupt_requested"] = False
        
    return state
