"""Chat Workflow 节点实现

对话相关节点：意图识别、上下文构建、记忆检索、生成回复
"""

import re
import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from ..state import AgentState, INTENT_CHAT, INTENT_DIARY, INTENT_SKILL, INTENT_CONTENT, INTENT_UNKNOWN
from huaqi_src.layers.capabilities.llm.manager import get_llm_manager
from huaqi_src.layers.data.profile.manager import get_profile_manager

logger = logging.getLogger(__name__)


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

    last_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_message = msg.content
            break

    if not last_message:
        return {"intent": INTENT_CHAT, "intent_confidence": 1.0}

    text = last_message.lower()
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return {"intent": intent, "intent_confidence": 0.8}

    return {"intent": INTENT_CHAT, "intent_confidence": 0.9}


def build_context(state: AgentState) -> Dict[str, Any]:
    """构建上下文节点

    组装系统提示词、人格画像、记忆、用户画像等
    """
    personality_context = state.get("personality_context", "")

    user_profile_context = ""
    try:
        profile_manager = get_profile_manager()
        user_profile_context = profile_manager.get_system_prompt_addition()
    except Exception:
        pass

    system_prompt = build_system_prompt(
        personality_context,
        user_profile_context,
    )

    workflow_data = state.get("workflow_data", {})
    workflow_data["system_prompt"] = system_prompt

    return {"workflow_data": workflow_data}


def build_system_prompt(
    personality_context: Optional[str] = None,
    user_profile_context: Optional[str] = None,
) -> str:
    """构建系统提示词"""
    base_prompt = """你是 Huaqi (花旗)，一个个人 AI 伴侣系统。

你的职责：
1. 作为用户的数字伙伴，提供陪伴和支持
2. 记住用户的重要信息和偏好
3. 帮助用户记录日记、追踪成长、管理目标
4. 在内容创作时提供协助
5. 当用户询问新闻、时事、世界动态时，必须先调用 search_worldnews_tool 查询本地数据；如果工具返回"本地未找到"或无结果，必须紧接着调用 google_search_tool 在互联网上搜索，不得直接回答

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


def extract_user_info(state: AgentState) -> Dict[str, Any]:
    """从用户消息中提取用户信息节点

    检测用户自我介绍并更新画像
    """
    messages = state.get("messages", [])

    last_message = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_message = msg.content
            break

    if not last_message:
        return {}

    try:
        from ...cli.context import build_llm_manager, ensure_initialized
        ensure_initialized()
        llm_mgr = build_llm_manager(temperature=0.3, max_tokens=500)

        profile_manager = get_profile_manager()
        if llm_mgr is not None:
            extracted = profile_manager.extract_from_message(last_message, llm_manager=llm_mgr)
        else:
            extracted = profile_manager.extract_from_message(last_message)

        if extracted:
            return {"user_info_extracted": extracted}

    except Exception:
        pass

    return {}


def retrieve_memories(state: AgentState) -> Dict[str, Any]:
    """检索记忆节点

    来源 1: Chroma 向量库（语义相关，覆盖历史）
    来源 2: 当天 Markdown 文件直接扫描（覆盖向量库尚未收录的今日对话）
    合并去重后注入 system prompt。
    """
    messages = state.get("messages", [])

    query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    if not query:
        return {"recent_memories": []}

    memories: List[str] = []

    try:
        from huaqi_src.layers.data.memory.vector import get_hybrid_search

        search = get_hybrid_search(use_vector=True, use_bm25=True)
        results = search.search(query, top_k=3)

        for r in results:
            content = r.get("content", "")
            if content:
                memories.append(content[:300])
    except Exception as e:
        logger.debug(f"向量库检索失败: {e}")

    try:
        from datetime import date as _date
        from ...config.paths import get_conversations_dir
        from huaqi_src.layers.data.memory.storage.markdown_store import MarkdownMemoryStore

        conversations_dir = get_conversations_dir()

        if conversations_dir.exists():
            today_str = _date.today().strftime("%Y%m%d")
            today_dir = conversations_dir / _date.today().strftime("%Y/%m")

            if today_dir.exists():
                query_lower = query.lower()
                keywords = [query_lower[i:i+2] for i in range(0, len(query_lower) - 1, 2)]
                keywords = [k for k in keywords if len(k) >= 2]
                if not keywords:
                    keywords = [query_lower]

                for md_file in sorted(today_dir.glob(f"{today_str}_*.md"), reverse=True)[:20]:
                    try:
                        content = md_file.read_text(encoding="utf-8")
                        content_lower = content.lower()
                        hit_keyword = next((k for k in keywords if k in content_lower), None)
                        if hit_keyword is None:
                            continue
                        lines = content.split("\n")
                        snippet_lines: List[str] = []
                        for i, line in enumerate(lines):
                            if hit_keyword in line.lower():
                                start = max(0, i - 2)
                                end = min(len(lines), i + 3)
                                snippet_lines.extend(lines[start:end])
                                snippet_lines.append("...")
                                if len(snippet_lines) > 15:
                                    break
                        snippet = "\n".join(snippet_lines[:15]).strip()
                        if snippet:
                            date_label = md_file.stem[:8]
                            memories.append(f"[今天 {date_label[4:6]}/{date_label[6:8]}]\n{snippet[:250]}")
                    except Exception:
                        continue
    except Exception as e:
        logger.debug(f"Markdown 今日记忆扫描失败: {e}")

    seen: set = set()
    unique_memories: List[str] = []
    for m in memories:
        key = m[:60]
        if key not in seen:
            seen.add(key)
            unique_memories.append(m)

    return {"recent_memories": unique_memories[:5]}


async def generate_response(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """生成回复节点

    调用 LLM 生成回复
    """
    messages = state.get("messages", [])
    workflow_data = state.get("workflow_data", {})
    memories = state.get("recent_memories", [])

    system_prompt = workflow_data.get("system_prompt", build_system_prompt())

    if memories:
        trimmed = [m[:200] for m in memories]
        combined = "\n".join([f"- {m}" for m in trimmed])
        if len(combined) > 1000:
            combined = combined[:1000] + "\n...(记忆截断)"
        system_prompt += f"\n\n相关历史记忆（自动检索）：\n{combined}"

    full_messages = [SystemMessage(content=system_prompt)] + messages

    try:
        from ...cli.context import build_llm_manager, ensure_initialized
        ensure_initialized()
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=1500)
        if llm_mgr is None:
            raise RuntimeError("未配置任何 LLM 提供商")

        active_name = llm_mgr.get_active_provider()
        if not active_name:
            raise RuntimeError("未配置任何 LLM 提供商")
        cfg = next(iter(llm_mgr._configs.values()))

        if "reasoner" in (cfg.model or "").lower():
            raise RuntimeError(
                f"模型 '{cfg.model}' 不支持工具调用（function calling）。"
                f"请运行 `huaqi config set llm_providers` 将模型改为 deepseek-chat。"
            )

        from langchain_openai import ChatOpenAI
        chat_model = ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=1,
            max_tokens=cfg.max_tokens,
            streaming=True,
        )

        from ..tools import _TOOL_REGISTRY
        chat_model_with_tools = chat_model.bind_tools(_TOOL_REGISTRY)

        response_msg = None
        async for chunk in chat_model_with_tools.astream(full_messages, config=config):
            if response_msg is None:
                response_msg = chunk
            else:
                response_msg += chunk

        return {
            "response": response_msg.content,
            "messages": [response_msg],
        }

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"generate_response 失败: {e}", exc_info=True)
        err_str = str(e)
        if "429" in err_str or "TooManyRequests" in err_str or "quota" in err_str.lower() or "服务树" in err_str:
            user_msg = f"API 调用失败（配额或权限问题）：{err_str[:200]}"
        elif "401" in err_str or "Unauthorized" in err_str or "authentication" in err_str.lower():
            user_msg = f"API 认证失败，请检查 API Key 配置：{err_str[:200]}"
        elif "timeout" in err_str.lower() or "timed out" in err_str.lower():
            user_msg = "LLM 请求超时，请稍后重试。"
        elif "Model Not Exist" in err_str or "model_not_found" in err_str.lower() or "invalid_request_error" in err_str.lower():
            user_msg = f"模型不存在，请运行 `huaqi config llm-setup` 重新配置正确的模型名称（如 deepseek-chat）：{err_str[:200]}"
        else:
            user_msg = f"生成回复失败：{err_str[:200]}"
        return {
            "error": f"生成回复失败: {err_str}",
            "response": user_msg,
            "messages": [AIMessage(content=user_msg)],
        }


def save_conversation(state: AgentState) -> Dict[str, Any]:
    """保存对话节点：Markdown 存档 + Chroma 向量索引"""
    messages = state.get("messages", [])
    response = state.get("response", "")

    if not response:
        return {}

    turns = []
    user_msg = ""
    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_msg = msg.content
        elif isinstance(msg, AIMessage) and user_msg:
            turns.append({"user_message": user_msg, "assistant_response": msg.content})
            user_msg = ""

    if not turns:
        return {}

    try:
        from datetime import datetime as dt
        from ...config.paths import get_conversations_dir
        from huaqi_src.layers.data.memory.storage.markdown_store import MarkdownMemoryStore

        now = dt.now()
        session_id = state.get("workflow_data", {}).get("thread_id", now.strftime("%Y%m%d_%H%M%S"))

        memory_store = MarkdownMemoryStore(get_conversations_dir())
        memory_store.save_conversation(
            session_id=session_id,
            timestamp=now,
            turns=turns,
            metadata={"intent": state.get("intent", "chat"), "turns": len(turns)},
        )

        _index_to_chroma(session_id, turns, now)

    except Exception:
        pass

    return {}


def _index_to_chroma(session_id: str, turns: List[Dict[str, Any]], timestamp) -> None:
    """将对话轮次写入 Chroma 向量库"""
    try:
        from huaqi_src.layers.data.memory.vector import get_chroma_client, get_embedding_service

        chroma = get_chroma_client()
        embedder = get_embedding_service()

        for i, turn in enumerate(turns):
            content = f"用户：{turn['user_message']}\nHuaqi：{turn['assistant_response']}"
            doc_id = f"{session_id}_turn_{i}"

            embedding = embedder.encode(content)

            chroma.add(
                doc_id=doc_id,
                content=content,
                metadata={
                    "session_id": session_id,
                    "turn_index": i,
                    "date": timestamp.strftime("%Y-%m-%d"),
                    "type": "conversation",
                },
                embedding=embedding.tolist() if hasattr(embedding, "tolist") else list(embedding),
            )
    except Exception:
        pass


def handle_error(state: AgentState) -> Dict[str, Any]:
    """错误处理节点"""
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


analyze_user_message = classify_intent
