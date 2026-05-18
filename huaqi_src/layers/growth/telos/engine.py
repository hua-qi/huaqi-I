import json
from datetime import datetime, timezone
from difflib import SequenceMatcher
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


_TELOS_FALLBACKS: dict[str, str] = {}


def _load_telos_prompt(scene_id: str, **kwargs) -> str:
    """加载 TELOS 引擎提示词，优先从 PromptLoader，回退到内置默认值。"""
    try:
        from huaqi_src.prompts.loader import get_prompt_loader
        loader = get_prompt_loader()
        system, user = loader.load(scene_id, **kwargs)
        return (system or "") + ("\n" + user if user else "")
    except Exception:
        import sys
        sys.stderr.write(f"[TELOS] PromptLoader 不可用，使用内置回退: {scene_id}\n")
        from huaqi_src.prompts._defaults import _BUILTIN_DEFAULTS
        raw = _BUILTIN_DEFAULTS.get(scene_id, "")
        if raw and kwargs:
            from huaqi_src.prompts.loader import PromptLoader
            system, user = PromptLoader._parse(raw)
            result = ""
            if system:
                result = system.format(**kwargs)
            if user:
                if result:
                    result += "\n"
                result += user.format(**kwargs)
            return result
        return raw


class ReviewOutput(BaseModel):
    is_stale: bool
    new_consistency_score: float
    reason: str


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def _skip_duplicate_update(old_content: str, new_content: str) -> bool:
    """True if new content is nearly identical to current, meaning update should be skipped."""
    if not new_content or not new_content.strip():
        return True
    return SequenceMatcher(None, old_content.strip(), new_content.strip()).ratio() > 0.95


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
        prompt = _load_telos_prompt(
            "layers.growth.telos.engine.step1",
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
        prompt = _load_telos_prompt(
            "layers.growth.telos.engine.step3",
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
        prompt = _load_telos_prompt(
            "layers.growth.telos.engine.step4",
            dimension=dimension,
            old_content=dim.content,
            signal_summaries="\n".join(f"- {s}" for s in signal_summaries),
            suggested_content=step3_result.suggested_content or "",
        )
        response = self._llm.invoke(prompt)
        data = _parse_json(response.content)
        result = Step4Output(**data)

        if _skip_duplicate_update(dim.content, result.new_content):
            return result

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

        prompt = _load_telos_prompt(
            "layers.growth.telos.engine.step5",
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
        prompt = _load_telos_prompt(
            "layers.growth.telos.engine.review_stale",
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
        prompt = _load_telos_prompt(
            "layers.growth.telos.engine.step345",
            telos_index=self._telos_index(),
            days=days,
            dimension=dimension,
            layer=dim.layer.value,
            count=len(signal_summaries),
            signal_summaries="\n".join(f"- {s}" for s in signal_summaries),
            current_content=dim.content,
        )
        response = await self._llm.ainvoke(prompt)
        data = _parse_json(response.content)
        result = CombinedStepOutput(**data)

        if _skip_duplicate_update(dim.content, result.new_content or ""):
            result.should_update = False
            return result

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
