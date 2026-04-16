import json
from typing import Any, Dict, Optional

from huaqi_src.layers.capabilities.onboarding.questionnaire import OnboardingSession
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSIONS, STANDARD_DIMENSION_LAYERS

_GENERATE_PROMPT = """\
根据用户的自述，为每个有回答的维度生成初始认知描述。
要求：
- 语言简洁，不要分析腔，像朋友在帮他整理想法
- 每个维度 50 字以内
- 没有回答的维度输出 null

用户回答：
{qa_text}

请为以下维度生成内容：{dimensions}

输出合法 JSON，格式：{{"dimension_name": "内容或 null"}}"""


class OnboardingTelosGenerator:

    def __init__(self, telos_manager: TelosManager, llm: Any) -> None:
        self._mgr = telos_manager
        self._llm = llm
        self._generated: Dict[str, Optional[str]] = {}

    def generate(self, session: OnboardingSession) -> None:
        pairs = session.get_answered_pairs()
        if not pairs:
            return

        qa_text = "\n".join(
            f"[{p.dimension}] {p.answer}" for p in pairs
            if p.dimension in STANDARD_DIMENSIONS
        )
        answered_dims = [p.dimension for p in pairs if p.dimension in STANDARD_DIMENSIONS]

        if not answered_dims:
            return

        prompt = _GENERATE_PROMPT.format(
            qa_text=qa_text,
            dimensions=", ".join(answered_dims),
        )
        response = self._llm.invoke(prompt)
        text = response.content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        generated: Dict[str, Optional[str]] = json.loads(text)
        self._generated = generated

        for dim_name, content in generated.items():
            if dim_name not in STANDARD_DIMENSIONS:
                continue
            if not content:
                continue
            try:
                dim = self._mgr.get(dim_name)
                if dim.content != "（待补充）":
                    continue
                from huaqi_src.layers.growth.telos.models import HistoryEntry
                from datetime import datetime, timezone
                entry = HistoryEntry(
                    version=1,
                    change="冷启动自述初始化",
                    trigger="用户问卷回答",
                    confidence=0.4,
                    updated_at=datetime.now(timezone.utc),
                )
                self._mgr.update(
                    name=dim_name,
                    new_content=content,
                    history_entry=entry,
                    confidence=0.4,
                )
            except Exception:
                continue

    def build_confirmation_summary(self) -> str:
        lines = ["我整理了一下你说的，看看我理解得对不对：", ""]
        for dim_name, content in self._generated.items():
            if content and dim_name in STANDARD_DIMENSIONS:
                layer = STANDARD_DIMENSION_LAYERS.get(dim_name)
                layer_label = {
                    "core": "核心认知",
                    "middle": "当前状态",
                    "surface": "近期关注",
                }.get(layer.value if layer else "", "")
                lines.append(f"- {layer_label}[{dim_name}]：{content}")
        lines += ["", "有没有哪里理解偏了？"]
        return "\n".join(lines)
