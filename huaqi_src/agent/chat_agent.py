"""ChatAgent - LangGraph 对话 Agent 封装

提供同步接口给 CLI 调用，内部使用 asyncio 驱动 LangGraph。
支持：流式输出、会话持久化（SqliteSaver）、会话新建/恢复。
"""

import asyncio
import queue
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, List, Optional

import yaml
from langchain_core.messages import HumanMessage

from .state import create_initial_state
from .graph.chat import compile_chat_graph


_SESSIONS_INDEX_FILENAME = "sessions_index.yaml"


def _get_sessions_index_path() -> Path:
    from ..config.paths import require_data_dir
    return require_data_dir() / _SESSIONS_INDEX_FILENAME


def load_sessions() -> List[dict]:
    """加载会话索引列表，按最后活跃时间倒序"""
    path = _get_sessions_index_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        sessions = data.get("sessions", [])
        return sorted(sessions, key=lambda s: s.get("last_active", ""), reverse=True)
    except Exception:
        return []


def _save_session_meta(thread_id: str, title: str, turns: int) -> None:
    """更新会话索引中的元数据"""
    path = _get_sessions_index_path()
    try:
        sessions: List[dict] = []
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            sessions = data.get("sessions", [])

        now = datetime.now().isoformat()
        existing = next((s for s in sessions if s["thread_id"] == thread_id), None)
        if existing:
            existing["last_active"] = now
            existing["turns"] = turns
        else:
            sessions.append({
                "thread_id": thread_id,
                "title": title,
                "created_at": now,
                "last_active": now,
                "turns": turns,
            })

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump({"sessions": sessions}, f, allow_unicode=True, default_flow_style=False)
    except Exception:
        pass


class ChatAgent:
    """LangGraph 对话 Agent

    用法：
        agent = ChatAgent()                   # 新建会话
        agent = ChatAgent(thread_id="xxx")    # 恢复已有会话

    流式回复（推荐）：
        for chunk in agent.stream("你好"):
            print(chunk, end="", flush=True)

    非流式：
        response = agent.run("你好")
    """

    def __init__(self, thread_id: Optional[str] = None):
        self.thread_id = thread_id or str(uuid.uuid4())
        self._graph = None
        self._turn_count = 0
        self._personality_context = self._load_personality_context()

    def _load_personality_context(self) -> Optional[str]:
        try:
            from ..cli.context import ensure_initialized
            import huaqi_src.cli.context as ctx
            ensure_initialized()
            p = ctx._personality.profile
            return f"你的名字是 {p.name}，角色是用户的{p.role}。"
        except Exception:
            return None

    def _make_config(self) -> dict:
        return {"configurable": {"thread_id": self.thread_id}}

    def stream(self, user_input: str) -> Iterator[str]:
        """流式输出，逐 token yield 给调用方"""
        _sentinel = object()
        q: queue.Queue = queue.Queue()

        async def _run():
            try:
                async for chunk in self._astream(user_input):
                    q.put(chunk)
            finally:
                q.put(_sentinel)

        t = threading.Thread(target=lambda: asyncio.run(_run()), daemon=True)
        t.start()

        while True:
            item = q.get()
            if item is _sentinel:
                break
            yield item

        t.join()

    async def _astream(self, user_input: str):
        state_input = {"messages": [HumanMessage(content=user_input)]}
        config = self._make_config()
        collected_chunks = []

        from .graph.chat import build_chat_graph
        workflow = build_chat_graph()

        try:
            import aiosqlite
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            from ..config.paths import require_data_dir
            db_path = require_data_dir() / "checkpoints.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
                graph = workflow.compile(checkpointer=checkpointer)
                async for event in graph.astream_events(state_input, config=config, version="v2"):
                    kind = event.get("event", "")
                    name = event.get("name", "")
                    if kind == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            collected_chunks.append(chunk.content)
                            yield chunk.content
                    elif kind == "on_chain_end" and name == "chat_response":
                        if not collected_chunks:
                            out = event.get("data", {}).get("output", {})
                            if isinstance(out, dict):
                                response_text = out.get("response", "")
                                if response_text and response_text != "抱歉，我现在有点忙，请稍后再试。":
                                    collected_chunks.append(response_text)
                                    yield response_text
        except ImportError:
            from langgraph.checkpoint.memory import MemorySaver
            graph = workflow.compile(checkpointer=MemorySaver())
            async for event in graph.astream_events(state_input, config=config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        collected_chunks.append(chunk.content)
                        yield chunk.content
                elif kind == "on_chain_end" and name == "chat_response":
                    if not collected_chunks:
                        out = event.get("data", {}).get("output", {})
                        if isinstance(out, dict):
                            response_text = out.get("response", "")
                            if response_text and response_text != "抱歉，我现在有点忙，请稍后再试。":
                                collected_chunks.append(response_text)
                                yield response_text

        self._turn_count += 1
        title = user_input[:20].replace("\n", " ")
        _save_session_meta(self.thread_id, title, self._turn_count)

        if not collected_chunks:
            yield "抱歉，我现在无法回复，请稍后再试。"

    async def resume(self, user_response: str) -> Iterator[str]:
        """恢复被中断的工作流"""
        from langchain_core.messages import Command
        
        config = self._make_config()
        collected_chunks = []
        
        from .graph.chat import build_chat_graph
        workflow = build_chat_graph()
        
        # 使用 Command 提供恢复数据
        command = Command(resume=user_response)
        
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            from ..config.paths import require_data_dir
            db_path = require_data_dir() / "checkpoints.db"
            
            async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
                graph = workflow.compile(checkpointer=checkpointer)
                async for event in graph.astream_events(command, config=config, version="v2"):
                    kind = event.get("event", "")
                    name = event.get("name", "")
                    if kind == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            collected_chunks.append(chunk.content)
                            yield chunk.content
                    elif kind == "on_chain_end" and name == "chat_response":
                        if not collected_chunks:
                            out = event.get("data", {}).get("output", {})
                            if isinstance(out, dict):
                                response_text = out.get("response", "")
                                if response_text:
                                    collected_chunks.append(response_text)
                                    yield response_text
        except ImportError:
            from langgraph.checkpoint.memory import MemorySaver
            graph = workflow.compile(checkpointer=MemorySaver())
            async for event in graph.astream_events(command, config=config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        collected_chunks.append(chunk.content)
                        yield chunk.content
                elif kind == "on_chain_end" and name == "chat_response":
                    if not collected_chunks:
                        out = event.get("data", {}).get("output", {})
                        if isinstance(out, dict):
                            response_text = out.get("response", "")
                            if response_text:
                                collected_chunks.append(response_text)
                                yield response_text
                                
        if not collected_chunks:
            yield "继续执行完成。"

    def run(self, user_input: str) -> str:
        """非流式调用，返回完整回复字符串"""
        chunks = list(self.stream(user_input))
        return "".join(chunks)

    def get_state(self) -> dict:
        """返回当前会话状态摘要"""
        try:
            config = self._make_config()
            state = self._graph.get_state(config)
            next_nodes = state.next if hasattr(state, "next") else []
            current_node = next_nodes[0] if next_nodes else "idle"
            return {
                "thread_id": self.thread_id,
                "current_node": current_node,
                "turn_count": self._turn_count,
            }
        except Exception:
            return {"thread_id": self.thread_id, "current_node": "unknown"}

    def reset(self) -> None:
        """新建会话（保留图实例，更换 thread_id）"""
        self.thread_id = str(uuid.uuid4())
        self._turn_count = 0
