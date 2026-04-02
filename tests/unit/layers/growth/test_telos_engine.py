import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from huaqi_src.layers.data.raw_signal.models import RawSignal, SourceType
from huaqi_src.layers.growth.telos.engine import (
    TelosEngine,
    Step1Output,
    Step3Output,
    Step4Output,
    Step5Output,
    SignalStrength,
    UpdateType,
)
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import DimensionLayer


@pytest.fixture
def telos_dir(tmp_path: Path) -> Path:
    d = tmp_path / "telos"
    d.mkdir()
    return d


@pytest.fixture
def telos_manager(telos_dir: Path) -> TelosManager:
    mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
    mgr.init()
    return mgr


@pytest.fixture
def journal_signal() -> RawSignal:
    return RawSignal(
        user_id="user_a",
        source_type=SourceType.JOURNAL,
        timestamp=datetime(2026, 1, 4, 10, 0, 0, tzinfo=timezone.utc),
        content="今天一直在想方向感的问题，感觉努力了很久但方向根本就错了，很迷茫。",
    )


@pytest.fixture
def mock_step1_strong() -> dict:
    return {
        "dimensions": ["challenges"],
        "emotion": "negative",
        "intensity": 0.8,
        "signal_strength": "strong",
        "strong_reason": "用户明确表达了困惑和方向迷失感",
        "summary": "用户对方向感感到迷茫，质疑努力的意义",
        "new_dimension_hint": None,
    }


@pytest.fixture
def mock_step1_weak() -> dict:
    return {
        "dimensions": ["learned"],
        "emotion": "neutral",
        "intensity": 0.3,
        "signal_strength": "weak",
        "strong_reason": None,
        "summary": "用户记录了今天读了一本书",
        "new_dimension_hint": None,
    }


@pytest.fixture
def mock_step1_new_dimension_hint() -> dict:
    return {
        "dimensions": [],
        "emotion": "positive",
        "intensity": 0.6,
        "signal_strength": "medium",
        "strong_reason": None,
        "summary": "用户记录了跑步 5 公里",
        "new_dimension_hint": "health",
    }


@pytest.fixture
def mock_step3_update() -> dict:
    return {
        "should_update": True,
        "update_type": "challenge",
        "confidence": 0.75,
        "reason": "连续 3 次提到方向感问题，质疑努力的价值",
        "suggested_content": "当前最大挑战是目标感缺失，努力方向比努力本身更重要",
    }


@pytest.fixture
def mock_step3_skip() -> dict:
    return {
        "should_update": False,
        "update_type": None,
        "confidence": 0.3,
        "reason": "信号太弱，尚不足以更新",
        "suggested_content": None,
    }


@pytest.fixture
def mock_step4() -> dict:
    return {
        "new_content": "当前最大挑战是目标感缺失，选择方向比埋头努力更重要。",
        "history_entry": {
            "change": "从「缺乏专注」更新为「目标感缺失」",
            "trigger": "日记连续 3 次提到方向感问题",
        },
    }


@pytest.fixture
def mock_step5_growth_event() -> dict:
    return {
        "is_growth_event": True,
        "narrative": "你开始意识到方向比努力更重要了。这个认知在过去一个月里反复被你的日记所印证。",
        "title": "开始质疑努力的方向",
    }


@pytest.fixture
def mock_step5_no_event() -> dict:
    return {
        "is_growth_event": False,
        "narrative": None,
        "title": None,
    }


class TestStep1Output:
    def test_valid_strong_signal(self, mock_step1_strong):
        out = Step1Output(**mock_step1_strong)
        assert out.signal_strength == SignalStrength.STRONG
        assert out.new_dimension_hint is None
        assert "challenges" in out.dimensions

    def test_valid_weak_signal(self, mock_step1_weak):
        out = Step1Output(**mock_step1_weak)
        assert out.signal_strength == SignalStrength.WEAK

    def test_new_dimension_hint_captured(self, mock_step1_new_dimension_hint):
        out = Step1Output(**mock_step1_new_dimension_hint)
        assert out.new_dimension_hint == "health"
        assert out.dimensions == []

    def test_intensity_range_validated(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Step1Output(
                dimensions=["beliefs"],
                emotion="positive",
                intensity=1.5,
                signal_strength="strong",
                strong_reason=None,
                summary="test",
                new_dimension_hint=None,
            )


class TestStep3Output:
    def test_should_update_true(self, mock_step3_update):
        out = Step3Output(**mock_step3_update)
        assert out.should_update is True
        assert out.update_type == UpdateType.CHALLENGE
        assert out.suggested_content is not None

    def test_should_update_false(self, mock_step3_skip):
        out = Step3Output(**mock_step3_skip)
        assert out.should_update is False
        assert out.update_type is None
        assert out.suggested_content is None


class TestStep4Output:
    def test_valid_output(self, mock_step4):
        out = Step4Output(**mock_step4)
        assert out.new_content
        assert out.history_entry["change"]
        assert out.history_entry["trigger"]


class TestStep5Output:
    def test_is_growth_event(self, mock_step5_growth_event):
        out = Step5Output(**mock_step5_growth_event)
        assert out.is_growth_event is True
        assert out.narrative is not None
        assert out.title is not None

    def test_not_growth_event(self, mock_step5_no_event):
        out = Step5Output(**mock_step5_no_event)
        assert out.is_growth_event is False
        assert out.narrative is None


class TestTelosEngineStep1:
    def test_step1_returns_step1_output(self, telos_manager, journal_signal, mock_step1_strong):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=__import__("json").dumps(mock_step1_strong))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = engine.step1_analyze(journal_signal)

        assert isinstance(result, Step1Output)
        assert "challenges" in result.dimensions

    def test_step1_injects_active_dimensions_into_prompt(self, telos_manager, journal_signal, mock_step1_strong):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=__import__("json").dumps(mock_step1_strong))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        engine.step1_analyze(journal_signal)

        call_args = mock_llm.invoke.call_args
        prompt_text = str(call_args)
        assert "beliefs" in prompt_text or "challenges" in prompt_text

    def test_step1_captures_new_dimension_hint(self, telos_manager, journal_signal, mock_step1_new_dimension_hint):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=__import__("json").dumps(mock_step1_new_dimension_hint))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = engine.step1_analyze(journal_signal)
        assert result.new_dimension_hint == "health"


class TestTelosEngineStep3:
    def test_step3_returns_step3_output(self, telos_manager, mock_step3_update):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=__import__("json").dumps(mock_step3_update))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        signal_summaries = ["用户对方向感感到迷茫"] * 3
        result = engine.step3_decide(
            dimension="challenges",
            signal_summaries=signal_summaries,
            days=30,
        )

        assert isinstance(result, Step3Output)
        assert result.should_update is True

    def test_step3_skip_does_not_call_step4(self, telos_manager, mock_step3_skip, mock_step4):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=__import__("json").dumps(mock_step3_skip))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        step3_result = engine.step3_decide(
            dimension="challenges",
            signal_summaries=["微弱信号"],
            days=7,
        )
        assert step3_result.should_update is False

        call_count_after_step3 = mock_llm.invoke.call_count
        assert call_count_after_step3 == 1


class TestTelosEngineStep4:
    def test_step4_returns_step4_output(self, telos_manager, mock_step3_update, mock_step4):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=__import__("json").dumps(mock_step4))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        step3 = Step3Output(**mock_step3_update)
        result = engine.step4_generate(
            dimension="challenges",
            step3_result=step3,
            signal_summaries=["信号摘要"],
        )

        assert isinstance(result, Step4Output)
        assert result.new_content
        assert len(result.new_content) <= 200

    def test_step4_updates_telos_manager(self, telos_manager, mock_step3_update, mock_step4):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=__import__("json").dumps(mock_step4))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        step3 = Step3Output(**mock_step3_update)
        engine.step4_generate(
            dimension="challenges",
            step3_result=step3,
            signal_summaries=["信号摘要"],
        )

        updated = telos_manager.get("challenges")
        assert updated.update_count == 1
        assert "目标感缺失" in updated.content or "方向" in updated.content


class TestTelosEngineStep5:
    def test_step5_core_layer_is_growth_event(self, telos_manager, mock_step4, mock_step5_growth_event):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=__import__("json").dumps(mock_step5_growth_event))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        step4 = Step4Output(**mock_step4)
        result = engine.step5_judge_growth(
            dimension="beliefs",
            layer=DimensionLayer.CORE,
            step4_result=step4,
        )

        assert isinstance(result, Step5Output)
        assert result.is_growth_event is True

    def test_step5_not_growth_event(self, telos_manager, mock_step4, mock_step5_no_event):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=__import__("json").dumps(mock_step5_no_event))
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        step4 = Step4Output(**mock_step4)
        result = engine.step5_judge_growth(
            dimension="learned",
            layer=DimensionLayer.SURFACE,
            step4_result=step4,
        )

        assert result.is_growth_event is False
        assert result.narrative is None


class TestTelosEngineFullPipeline:
    def test_run_pipeline_skip_when_step3_no_update(
        self, telos_manager, journal_signal, mock_step1_strong, mock_step3_skip
    ):
        import json
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content=json.dumps(mock_step1_strong)),
            MagicMock(content=json.dumps(mock_step3_skip)),
        ]
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = engine.run_pipeline(
            signal=journal_signal,
            step1_result=Step1Output(**mock_step1_strong),
            signal_summaries=["摘要1"],
            days=30,
        )

        assert result["growth_event"] is None
        assert result["updated"] is False

    def test_run_pipeline_full_update(
        self,
        telos_manager,
        journal_signal,
        mock_step1_strong,
        mock_step3_update,
        mock_step4,
        mock_step5_growth_event,
    ):
        import json
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content=json.dumps(mock_step3_update)),
            MagicMock(content=json.dumps(mock_step4)),
            MagicMock(content=json.dumps(mock_step5_growth_event)),
        ]
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = engine.run_pipeline(
            signal=journal_signal,
            step1_result=Step1Output(**mock_step1_strong),
            signal_summaries=["摘要1", "摘要2", "摘要3"],
            days=30,
        )

        assert result["updated"] is True
        assert result["growth_event"] is not None
        assert result["growth_event"].is_growth_event is True
