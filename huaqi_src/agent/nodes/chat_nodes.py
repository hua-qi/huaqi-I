"""Chat Workflow 节点实现

对话相关节点：意图识别、上下文构建、记忆检索、生成回复
使用自适应用户理解系统，支持动态维度
"""

import re
import asyncio
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..state import AgentState, INTENT_CHAT, INTENT_DIARY, INTENT_SKILL, INTENT_CONTENT, INTENT_UNKNOWN
from ...core.adaptive_understanding import get_adaptive_understanding
from ...core.llm import get_llm_manager
from ...core.user_profile import get_profile_manager

# 缓存上次的分析结果
_user_last_result: Optional[Any] = None


# 简单的意图分类规则
INTENT_PATTERNS = {
    INTENT_DIARY: [
        r".*?(写日记|查看日记|日记列表|搜索日记).*?",
        r".*?日记.*?",
    ],
    INTENT_SKILL: [
        r".*?(技能|成长|目标|习惯|打卡).*?",
        r".*?(学习了|练习了|完成了).*?",
    ],
    INTENT_CONTENT: [
        r".*?(发布|生成内容|小红书|微博|文案).*?",
    ],
}


def classify_intent(state: AgentState) -> Dict[str, Any]:
    """意图识别节点
    
    简单规则分类，后续可以替换为 LLM 分类
    """
    messages = state.get("messages", [])
    if not messages:
        return {"intent": INTENT_CHAT, "intent_confidence": 1.0}
    
    # 获取最后一条用户消息
    last_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_message = msg.content
            break
    
    if not last_message:
        return {"intent": INTENT_CHAT, "intent_confidence": 1.0}
    
    # 规则匹配
    text = last_message.lower()
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return {"intent": intent, "intent_confidence": 0.8}
    
    # 默认意图
    return {"intent": INTENT_CHAT, "intent_confidence": 0.9}


def build_context(state: AgentState) -> Dict[str, Any]:
    """构建上下文节点

    组装系统提示词、人格画像、记忆、用户理解洞察等
    """
    # 获取人格画像上下文
    personality_context = state.get("personality_context", "")

    # 获取用户画像上下文
    user_profile_context = ""
    try:
        profile_manager = get_profile_manager()
        user_profile_context = profile_manager.get_system_prompt_addition()
    except Exception:
        pass

    # 获取自适应理解上下文
    user_insight_context = ""
    
    try:
        adaptive = get_adaptive_understanding()
        user_insight_context = adaptive.get_context_for_response(
            current_result=_user_last_result,
        )
    except Exception:
        pass

    # 构建系统提示词
    system_prompt = build_system_prompt(
        personality_context,
        user_profile_context,
        user_insight_context,
    )

    # 更新 workflow_data
    workflow_data = state.get("workflow_data", {})
    workflow_data["system_prompt"] = system_prompt

    return {"workflow_data": workflow_data}


def build_system_prompt(
    personality_context: Optional[str] = None,
    user_profile_context: Optional[str] = None,
    user_insight_context: Optional[str] = None,
) -> str:
    """构建系统提示词"""
    base_prompt = """你是 Huaqi (花旗)，一个个人 AI 伴侣系统。

你的职责：
1. 作为用户的数字伙伴，提供陪伴和支持
2. 记住用户的重要信息和偏好
3. 帮助用户记录日记、追踪成长、管理目标
4. 在内容创作时提供协助

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

    # 添加用户画像信息
    if user_profile_context:
        base_prompt += f"\n{user_profile_context}\n"

    # 添加用户理解洞察
    if user_insight_context:
        base_prompt += f"\n{user_insight_context}\n"

    return base_prompt


def extract_user_info(state: AgentState) -> Dict[str, Any]:
    """从用户消息中提取用户信息节点
    
    检测用户自我介绍并更新画像
    """
    messages = state.get("messages", [])

    # 获取最后一条用户消息
    last_message = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_message = msg.content
            break

    if not last_message:
        return {}

    try:
        profile_manager = get_profile_manager()
        extracted = profile_manager.extract_from_message(last_message)

        if extracted:
            return {"user_info_extracted": extracted}

    except Exception:
        pass

    return {}


def analyze_user_understanding(state: AgentState) -> Dict[str, Any]:
    """分析用户理解节点
    
    使用自适应用户理解系统分析消息，支持动态维度发现
    """
    messages = state.get("messages", [])
    conversation_id = state.get("conversation_id", "")

    # 获取最后一条用户消息
    last_message = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_message = msg.content
            break

    if not last_message:
        return {"user_insight": None}

    try:
        # 获取自适应理解系统
        adaptive = get_adaptive_understanding()

        # 分析消息
        result = asyncio.run(adaptive.analyze(
            message=last_message,
            conversation_id=conversation_id,
            context={
                "history_turns": len(messages),
            }
        ))

        # 更新缓存
        global _user_last_result
        _user_last_result = result

        return {
            "user_insight": result.to_dict(),
            "proposed_dimensions": result.proposed_dimensions,
        }

    except Exception as e:
        # 分析失败不影响主流程
        return {"user_insight": None, "insight_error": str(e)}


def retrieve_memories(state: AgentState) -> Dict[str, Any]:
    """检索记忆节点
    
    从向量库中检索相关记忆
    """
    messages = state.get("messages", [])
    
    # 获取最后一条用户消息作为查询
    query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break
    
    if not query:
        return {"recent_memories": []}
    
    try:
        # 使用混合检索获取相关记忆
        from ...memory.vector import get_hybrid_search
        
        search = get_hybrid_search(use_vector=False, use_bm25=True)
        results = search.search(query, top_k=3)
        
        memories = []
        for r in results:
            content = r.get("content", "")
            if content:
                memories.append(content)
        
        return {"recent_memories": memories}
        
    except Exception as e:
        # 检索失败不影响主流程
        return {"recent_memories": []}


def generate_response(state: AgentState, llm_client=None) -> Dict[str, Any]:
    """生成回复节点
    
    调用 LLM 生成回复
    """
    messages = state.get("messages", [])
    workflow_data = state.get("workflow_data", {})
    memories = state.get("recent_memories", [])
    
    # 构建消息列表
    system_prompt = workflow_data.get("system_prompt", build_system_prompt())
    
    # 添加记忆上下文
    if memories:
        memory_text = "\n\n相关记忆：\n" + "\n".join([f"- {m}" for m in memories])
        system_prompt += memory_text
    
    # 构建完整消息列表
    full_messages = [SystemMessage(content=system_prompt)] + messages
    
    try:
        # 调用 LLM
        if llm_client is None:
            # 使用默认 LLM
            from ...core.llm import LLMManager
            llm = LLMManager()
            response = llm.chat(full_messages)
        else:
            response = llm_client.chat(full_messages)
        
        # 提取回复内容
        content = response
        if hasattr(response, 'content'):
            content = response.content
        
        return {
            "response": content,
            "messages": [AIMessage(content=content)],
        }
        
    except Exception as e:
        error_msg = f"生成回复失败: {str(e)}"
        return {
            "error": error_msg,
            "response": "抱歉，我现在有点忙，请稍后再试。",
            "messages": [AIMessage(content="抱歉，我现在有点忙，请稍后再试。")],
        }


def save_conversation(state: AgentState) -> Dict[str, Any]:
    """保存对话节点"""
    # 这里可以实现对话历史持久化
    # 暂时不做实际存储
    return {}


def handle_error(state: AgentState) -> Dict[str, Any]:
    """错误处理节点"""
    error = state.get("error")
    retry_count = state.get("retry_count", 0)
    
    if retry_count < 3:
        return {
            "retry_count": retry_count + 1,
            "error": None,
        }
    else:
        return {
            "response": "抱歉，我遇到了一些问题，让我们重新开始吧。",
            "messages": [AIMessage(content="抱歉，我遇到了一些问题，让我们重新开始吧。")],
            "error": None,
            "retry_count": 0,
        }


# 兼容旧接口
analyze_user_message = analyze_user_understanding
