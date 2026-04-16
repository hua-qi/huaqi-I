import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from huaqi_src.layers.data.raw_signal.models import RawSignal
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import (
    DimensionLayer,
    HistoryEntry,
    STANDARD_DIMENSION_LAYERS,
)


class SignalStrength(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class UpdateType(str, Enum):
    REINFORCE = "reinforce"
    CHALLENGE = "challenge"
    NEW = "new"


class Step1Output(BaseModel):
    dimensions: List[str]
    emotion: str
    intensity: float
    signal_strength: SignalStrength
    strong_reason: Optional[str]
    summary: str
    new_dimension_hint: Optional[str]
    has_people: bool = False
    mentioned_names: List[str] = Field(default_factory=list)

    @field_validator("intensity")
    @classmethod
    def intensity_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("intensity must be between 0.0 and 1.0")
        return v


class Step3Output(BaseModel):
    should_update: bool
    update_type: Optional[UpdateType]
    confidence: float
    reason: str
    suggested_content: Optional[str]


class Step4Output(BaseModel):
    new_content: str
    history_entry: Dict[str, str]


class Step5Output(BaseModel):
    is_growth_event: bool
    narrative: Optional[str]
    title: Optional[str]


class CombinedStepOutput(BaseModel):
    should_update: bool
    new_content: Optional[str]
    consistency_score: float
    history_entry: Optional[Dict[str, str]]
    is_growth_event: bool
    growth_title: Optional[str]
    growth_narrative: Optional[str]
    confidence: float = 0.0


_STEP1_PROMPT = """\
你是用户的个人成长分析师。
你的任务是分析用户的输入信号，判断它对用户的自我认知有什么影响。

以下是当前对这个用户的了解（TELOS 索引）：
{telos_index}

当前活跃维度：{active_dimensions}

分析以下输入信号：
来源：{source_type}
时间：{timestamp}
内容：{content}

请从以上活跃维度中判断本条信号涉及哪些维度。
如果信号内容不属于任何现有维度，请在 new_dimension_hint 字段说明。

输出合法 JSON，不要有任何额外文字：
{{
  "dimensions": ["..."],
  "emotion": "positive|negative|neutral",
  "intensity": 0.0-1.0,
  "signal_strength": "strong|medium|weak",
  "strong_reason": "...",
  "summary": "...",
  "new_dimension_hint": null,
  "has_people": true/false,
  "mentioned_names": ["姓名1", "姓名2"]
}}"""

_STEP3_PROMPT = """\
你是用户的个人成长分析师。
你的任务是判断积累的信号是否说明用户的某个认知发生了变化。

以下是当前对这个用户的了解：
{telos_index}

以下是最近 {days} 天，关于「{dimension}」维度的 {count} 条信号摘要：
{signal_summaries}

当前该维度的认知是：
{current_content}

输出合法 JSON，不要有任何额外文字：
{{
  "should_update": true/false,
  "update_type": "reinforce|challenge|new|null",
  "confidence": 0.0-1.0,
  "reason": "...",
  "suggested_content": "..."
}}"""

_STEP4_PROMPT = """\
你是用户的个人成长分析师。
你的任务是用自然、简洁的语言描述用户认知的变化。
写给用户自己看，不要用分析腔，要像朋友在帮他整理想法。

维度：{dimension}
旧版本内容：{old_content}
触发这次更新的信号摘要：{signal_summaries}
更新建议：{suggested_content}

输出合法 JSON，不要有任何额外文字：
{{
  "new_content": "...",
  "history_entry": {{
    "change": "...",
    "trigger": "..."
  }}
}}"""

_STEP5_PROMPT = """\
你是用户的个人成长见证者。
你的任务是识别用户真正有意义的内在变化，用温暖的语言记录下来。

判断标准：
- 核心层维度变化 → 几乎总是值得
- 中间层维度的方向性转变 → 值得
- 表面层的日常积累 → 通常不值得

维度：{dimension}（{layer}层）
变化前：{old_content}
变化后：{new_content}
更新原因：{trigger}

输出合法 JSON，不要有任何额外文字：
{{
  "is_growth_event": true/false,
  "narrative": "...",
  "title": "..."
}}"""

_REVIEW_STALE_PROMPT = """\
你是用户的个人成长分析师。
该维度已超过 {days} 天没有收到新信号。
请判断当前认知是否可能已经过时。

维度：{dimension}
当前认知：
{current_content}

请判断：
1. 内容是否可能已过时？（考虑时间流逝、人的变化、情境变化）
2. 如果过时，置信度应该降低多少？（new_consistency_score 应在 0.0~0.6 之间）
3. 如果仍然有效，维持 consistency_score 不变

输出合法 JSON，不要有任何额外文字：
{{
  "is_stale": true/false,
  "new_consistency_score": 0.0-1.0,
  "reason": "..."
}}\
"""


class ReviewOutput(BaseModel):
    is_stale: bool
    new_consistency_score: float
    reason: str


_STEP345_COMBINED_PROMPT = """\
你是用户的个人成长分析师兼见证者。
请同时完成三件事：
1. 判断是否应更新「{dimension}」维度的认知
2. 如果更新，生成新的认知内容和历史记录
3. 判断这次变化是否是值得记录的成长事件

以下是当前对这个用户的了解：
{telos_index}

以下是最近 {days} 天，关于「{dimension}」维度的 {count} 条信号摘要：
{signal_summaries}

当前该维度的认知是：
{current_content}

判断标准（成长事件）：
- 核心层维度变化 → 几乎总是值得
- 中间层维度的方向性转变 → 值得
- 表面层的日常积累 → 通常不值得

consistency_score 的含义：这些信号指向同一个方向的程度（0.0=完全矛盾，1.0=高度一致）

输出合法 JSON，不要有任何额外文字：
{{
  "should_update": true/false,
  "new_content": "...",
  "consistency_score": 0.0-1.0,
  "history_entry": {{
    "change": "...",
    "trigger": "..."
  }},
  "is_growth_event": true/false,
  "growth_title": "...",
  "growth_narrative": "..."
}}\
"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


class TelosEngine:

    def __init__(self, telos_manager: TelosManager, llm: Any) -> None:
        self._mgr = telos_manager
        self._llm = llm

    def _telos_index(self) -> str:
        index_path = self._mgr._dir / "INDEX.md"
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return ""

    def _active_dimension_names(self) -> List[str]:
        return [d.name for d in self._mgr.list_active()]

    def step1_analyze(self, signal: RawSignal) -> Step1Output:
        active_dims = self._active_dimension_names()
        prompt = _STEP1_PROMPT.format(
            telos_index=self._telos_index(),
            active_dimensions=", ".join(active_dims),
            source_type=signal.source_type.value,
            timestamp=signal.timestamp.isoformat(),
            content=signal.content,
        )
        response = self._llm.invoke(prompt)
        data = _parse_json(response.content)
        return Step1Output(**data)

    def step3_decide(
        self,
        dimension: str,
        signal_summaries: List[str],
        days: int,
    ) -> Step3Output:
        dim = self._mgr.get(dimension)
        prompt = _STEP3_PROMPT.format(
            telos_index=self._telos_index(),
            days=days,
            dimension=dimension,
            count=len(signal_summaries),
            signal_summaries="\n".join(f"- {s}" for s in signal_summaries),
            current_content=dim.content,
        )
        response = self._llm.invoke(prompt)
        data = _parse_json(response.content)
        return Step3Output(**data)

    def step4_generate(
        self,
        dimension: str,
        step3_result: Step3Output,
        signal_summaries: List[str],
    ) -> Step4Output:
        dim = self._mgr.get(dimension)
        prompt = _STEP4_PROMPT.format(
            dimension=dimension,
            old_content=dim.content,
            signal_summaries="\n".join(f"- {s}" for s in signal_summaries),
            suggested_content=step3_result.suggested_content or "",
        )
        response = self._llm.invoke(prompt)
        data = _parse_json(response.content)
        result = Step4Output(**data)

        version = dim.update_count + 1
        entry = HistoryEntry(
            version=version,
            change=result.history_entry["change"],
            trigger=result.history_entry["trigger"],
            confidence=step3_result.confidence,
            updated_at=datetime.now(timezone.utc),
        )
        self._mgr.update(
            name=dimension,
            new_content=result.new_content,
            history_entry=entry,
            confidence=step3_result.confidence,
        )
        return result

    def step5_judge_growth(
        self,
        dimension: str,
        layer: DimensionLayer,
        step4_result: Step4Output,
    ) -> Step5Output:
        dim = self._mgr.get(dimension)
        old_content = ""
        if dim.history:
            old_content = dim.history[-2].change if len(dim.history) >= 2 else ""

        prompt = _STEP5_PROMPT.format(
            dimension=dimension,
            layer=layer.value,
            old_content=old_content,
            new_content=step4_result.new_content,
            trigger=step4_result.history_entry.get("trigger", ""),
        )
        response = self._llm.invoke(prompt)
        data = _parse_json(response.content)
        return Step5Output(**data)

    def review_stale_dimension(
        self,
        dimension: str,
        days_since_last_signal: int,
    ) -> ReviewOutput:
        dim = self._mgr.get(dimension)
        prompt = _REVIEW_STALE_PROMPT.format(
            days=days_since_last_signal,
            dimension=dimension,
            current_content=dim.content,
        )
        response = self._llm.invoke(prompt)
        data = _parse_json(response.content)
        result = ReviewOutput(**data)

        if result.is_stale:
            count_score = min(dim.update_count / 10, 1.0)
            new_confidence = count_score * 0.4 + result.new_consistency_score * 0.6
            entry = HistoryEntry(
                version=dim.update_count + 1,
                change=f"定时复审：{result.reason}",
                trigger=f"超过 {days_since_last_signal} 天无新信号",
                confidence=new_confidence,
                updated_at=datetime.now(timezone.utc),
            )
            self._mgr.update(
                name=dimension,
                new_content=dim.content,
                history_entry=entry,
                confidence=new_confidence,
            )

        return result

    async def step345_combined(
        self,
        dimension: str,
        signal_summaries: List[str],
        days: int,
        recent_signal_count: int,
    ) -> CombinedStepOutput:
        dim = self._mgr.get(dimension)
        prompt = _STEP345_COMBINED_PROMPT.format(
            telos_index=self._telos_index(),
            days=days,
            dimension=dimension,
            count=len(signal_summaries),
            signal_summaries="\n".join(f"- {s}" for s in signal_summaries),
            current_content=dim.content,
        )
        response = await self._llm.ainvoke(prompt)
        data = _parse_json(response.content)
        result = CombinedStepOutput(**data)

        count_score = min(recent_signal_count / 10, 1.0)
        consistency_score = result.consistency_score
        result.confidence = count_score * 0.4 + consistency_score * 0.6

        if result.should_update and result.new_content and result.history_entry:
            version = dim.update_count + 1
            entry = HistoryEntry(
                version=version,
                change=result.history_entry["change"],
                trigger=result.history_entry["trigger"],
                confidence=result.confidence,
                updated_at=datetime.now(timezone.utc),
            )
            self._mgr.update(
                name=dimension,
                new_content=result.new_content,
                history_entry=entry,
                confidence=result.confidence,
            )

        return result

    def run_pipeline(
        self,
        signal: RawSignal,
        step1_result: Step1Output,
        signal_summaries: List[str],
        days: int,
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {"updated": False, "growth_event": None}

        for dimension in step1_result.dimensions:
            try:
                layer = STANDARD_DIMENSION_LAYERS.get(dimension, DimensionLayer.SURFACE)
                step3 = self.step3_decide(dimension, signal_summaries, days)
                if not step3.should_update:
                    continue

                step4 = self.step4_generate(dimension, step3, signal_summaries)
                results["updated"] = True

                step5 = self.step5_judge_growth(dimension, layer, step4)
                if step5.is_growth_event:
                    results["growth_event"] = step5

            except Exception:
                continue

        return results
