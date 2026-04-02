from typing import Any, List, Optional

from huaqi_src.agent.state import AgentState
from huaqi_src.layers.growth.telos.manager import TelosManager

_PART1_CHAT = """\
你是 Huaqi，用户的个人成长伙伴。
你了解这个用户——他们的信念、目标、挑战、成长历程。
你的回应要基于对他们的真实了解，而不是泛泛而谈。
语气：温暖、直接、有洞察力。不说废话，不说教。"""

_PART1_ONBOARDING = """\
你是 Huaqi，用户的个人成长伙伴。
这是你们第一次见面。你正在通过对话了解这个用户。
语气：像朋友第一次深聊，好奇、温暖、不评判。
每次只问一个问题，认真回应用户的每一个回答。"""

_PART1_REPORT = """\
你是 Huaqi，用户的个人成长伙伴。
你正在为用户生成成长回顾报告。
语气：客观、温暖、有洞察力。用数据说话，但不冷漠。"""

_PART1_DISTILL = """\
你是 Huaqi，用户的个人成长伙伴。
你正在分析用户最近的输入信号，提炼成长洞察。
专注于模式识别，不要过度解读单条信号。"""

_PART1_MAP = {
    "chat": _PART1_CHAT,
    "onboarding": _PART1_ONBOARDING,
    "report": _PART1_REPORT,
    "distill": _PART1_DISTILL,
}


class TelosContextBuilder:
    """将 TELOS 成长层数据组装为 AgentState 的三个上下文字段。"""

    def __init__(
        self,
        telos_manager: TelosManager,
        vector_search: Optional[Any] = None,
    ) -> None:
        self._mgr = telos_manager
        self._vector_search = vector_search

    def build_telos_snapshot(self) -> str:
        index_path = self._mgr._dir / "INDEX.md"
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        dims = self._mgr.list_active()
        lines = ["# 当前 TELOS 快照", ""]
        for d in dims:
            lines.append(f"- {d.name}（{d.layer.value}层，置信度 {d.confidence}）：{d.content[:60]}")
        return "\n".join(lines)

    def build_relevant_history(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[str]:
        if self._vector_search is None:
            return []
        try:
            results = self._vector_search.search(query, top_k=top_k)
            return [r["content"] for r in results[:top_k] if r.get("content")]
        except Exception:
            return []

    def inject(
        self,
        state: AgentState,
        query: Optional[str] = None,
    ) -> AgentState:
        telos_snapshot = self.build_telos_snapshot()
        relevant_history = self.build_relevant_history(query, top_k=5) if query else []

        return {
            **state,
            "telos_snapshot": telos_snapshot,
            "relevant_history": relevant_history,
        }


class SystemPromptBuilder:
    """将 AgentState 的三个上下文字段拼装成完整 system prompt。"""

    def build(
        self,
        telos_snapshot: str,
        relevant_history: List[str],
        interaction_mode: str,
    ) -> str:
        part1 = _PART1_MAP.get(interaction_mode, _PART1_CHAT)

        parts = [part1]

        if telos_snapshot:
            parts += [
                "",
                "## 你对这个用户的了解（TELOS）",
                "",
                telos_snapshot.strip(),
            ]

        if relevant_history:
            parts += [
                "",
                "## 相关历史记忆",
                "",
            ]
            for h in relevant_history:
                parts.append(f"- {h.strip()}")

        return "\n".join(parts)
