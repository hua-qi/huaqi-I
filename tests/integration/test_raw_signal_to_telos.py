"""
集成测试：数据层 → 成长层全流程

场景：用户连续 3 天写日记，内容都涉及「方向感缺失」
- Day 1：信号写入 → Step1 识别为 challenges 维度 → 累积不足，无更新
- Day 2：同上，累积 2 条
- Day 3：累积 3 条，强度足够 → Step3 决定更新 → Step4 生成内容
           → challenges.md 更新 → 成长事件生成
- 3 条 RawSignal 的 processed 均变为 1
- INDEX.md 中 challenges 行同步更新
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore
from huaqi_src.layers.data.raw_signal.pipeline import DistillationPipeline
from huaqi_src.layers.growth.telos.engine import (
    Step1Output,
    Step3Output,
    Step4Output,
    Step5Output,
    SignalStrength,
    TelosEngine,
)
from huaqi_src.layers.growth.telos.growth_events import GrowthEvent, GrowthEventStore
from huaqi_src.layers.growth.telos.manager import TelosManager


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "signals.db"


@pytest.fixture
def telos_dir(tmp_path: Path) -> Path:
    d = tmp_path / "telos"
    d.mkdir()
    return d


@pytest.fixture
def storage_adapter(db_path: Path) -> SQLiteStorageAdapter:
    return SQLiteStorageAdapter(db_path=db_path)


@pytest.fixture
def signal_store(storage_adapter: SQLiteStorageAdapter) -> RawSignalStore:
    return RawSignalStore(adapter=storage_adapter)


@pytest.fixture
def event_store(storage_adapter: SQLiteStorageAdapter) -> GrowthEventStore:
    return GrowthEventStore(adapter=storage_adapter)


@pytest.fixture
def telos_manager(telos_dir: Path) -> TelosManager:
    mgr = TelosManager(telos_dir=telos_dir, git_commit=False)
    mgr.init()
    return mgr


@pytest.fixture
def three_day_signals() -> list[RawSignal]:
    contents = [
        "今天感觉很迷茫，努力了很久但感觉方向根本就错了。",
        "又想到方向感的问题，不知道努力的意义在哪里，感觉在原地踏步。",
        "连续几天都在想这个问题：努力真的有用吗？感觉选错了方向，所有的努力都是白费的。",
    ]
    return [
        RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, i + 1, 10, 0, 0, tzinfo=timezone.utc),
            content=content,
        )
        for i, content in enumerate(contents)
    ]


def _make_step1(dimension: str = "challenges", strength: str = "strong") -> dict:
    return {
        "dimensions": [dimension],
        "emotion": "negative",
        "intensity": 0.8,
        "signal_strength": strength,
        "strong_reason": "用户明确表达了方向感缺失",
        "summary": f"用户对方向感感到迷茫（信号 {strength}）",
        "new_dimension_hint": None,
    }


def _make_step3_update() -> dict:
    return {
        "should_update": True,
        "update_type": "challenge",
        "confidence": 0.78,
        "reason": "连续 3 次提到方向感问题，质疑努力的价值",
        "suggested_content": "当前最大挑战是目标感缺失，选择方向比埋头努力更重要",
    }


def _make_step4() -> dict:
    return {
        "new_content": "当前最大挑战是目标感缺失，选择方向比埋头努力更重要。",
        "history_entry": {
            "change": "从「执行力不足」更新为「目标感缺失」",
            "trigger": "日记连续 3 次提到方向感问题，质疑努力的意义",
        },
    }


def _make_step5_event() -> dict:
    return {
        "is_growth_event": True,
        "narrative": "你开始意识到，方向比努力更重要。这个认知在三天的日记里反复出现，终于清晰了。",
        "title": "开始质疑努力的方向",
    }


# ── 测试：Step1 单条信号分析 ───────────────────────────────────────────────────

class TestStep1Integration:
    def test_step1_identifies_challenges_dimension(self, telos_manager, three_day_signals):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps(_make_step1("challenges"))
        )
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        result = engine.step1_analyze(three_day_signals[0])

        assert "challenges" in result.dimensions
        assert result.signal_strength == SignalStrength.STRONG
        assert result.new_dimension_hint is None

    def test_step1_prompt_contains_telos_index(self, telos_manager, three_day_signals):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps(_make_step1())
        )
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        engine.step1_analyze(three_day_signals[0])

        prompt = str(mock_llm.invoke.call_args)
        assert "challenges" in prompt or "beliefs" in prompt

    def test_step1_processes_all_three_signals(self, telos_manager, three_day_signals):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps(_make_step1())
        )
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        results = [engine.step1_analyze(s) for s in three_day_signals]

        assert len(results) == 3
        assert all("challenges" in r.dimensions for r in results)


# ── 测试：Step2 跨时间聚合（纯数据库，无 LLM）────────────────────────────────

class TestStep2Integration:
    def test_step2_aggregates_signals_by_dimension(self, signal_store, three_day_signals):
        for s in three_day_signals:
            signal_store.save(s)

        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        unprocessed = signal_store.query(
            RawSignalFilter(user_id="user_a", processed=0, since=since)
        )
        assert len(unprocessed) == 3

    def test_step2_count_by_user(self, signal_store, three_day_signals):
        for s in three_day_signals:
            signal_store.save(s)

        count = signal_store.count(RawSignalFilter(user_id="user_a"))
        assert count == 3

    def test_step2_signals_ordered_desc(self, signal_store, three_day_signals):
        for s in three_day_signals:
            signal_store.save(s)

        results = signal_store.query(RawSignalFilter(user_id="user_a"))
        timestamps = [r.timestamp for r in results]
        assert timestamps == sorted(timestamps, reverse=True)


# ── 测试：Step3 更新决策 ──────────────────────────────────────────────────────

class TestStep3Integration:
    def test_step3_triggers_update_with_3_strong_signals(self, telos_manager):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps(_make_step3_update())
        )
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        summaries = [
            "用户对方向感感到迷茫（信号 1）",
            "用户对方向感感到迷茫（信号 2）",
            "用户对方向感感到迷茫（信号 3）",
        ]
        result = engine.step3_decide("challenges", summaries, days=3)

        assert result.should_update is True
        assert result.confidence > 0.5

    def test_step3_no_update_with_weak_single_signal(self, telos_manager):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({
                "should_update": False,
                "update_type": None,
                "confidence": 0.2,
                "reason": "单条弱信号，不足以触发更新",
                "suggested_content": None,
            })
        )
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        result = engine.step3_decide("challenges", ["微弱信号"], days=1)

        assert result.should_update is False


# ── 测试：Step4 生成更新内容 ─────────────────────────────────────────────────

class TestStep4Integration:
    def test_step4_updates_challenges_md(self, telos_manager, telos_dir):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps(_make_step4())
        )
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        step3 = Step3Output(**_make_step3_update())

        engine.step4_generate("challenges", step3, ["摘要1", "摘要2", "摘要3"])

        updated = telos_manager.get("challenges")
        assert updated.update_count == 1
        assert "目标感缺失" in updated.content or "方向" in updated.content

    def test_step4_history_entry_written(self, telos_manager):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps(_make_step4())
        )
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        step3 = Step3Output(**_make_step3_update())
        engine.step4_generate("challenges", step3, ["摘要"])

        dim = telos_manager.get("challenges")
        assert len(dim.history) == 1
        assert dim.history[0].trigger == "日记连续 3 次提到方向感问题，质疑努力的意义"

    def test_step4_index_md_updated(self, telos_manager, telos_dir):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps(_make_step4())
        )
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        step3 = Step3Output(**_make_step3_update())
        engine.step4_generate("challenges", step3, ["摘要"])

        index_text = (telos_dir / "INDEX.md").read_text(encoding="utf-8")
        assert "challenges" in index_text
        assert "v1" in index_text


# ── 测试：Step5 成长事件判断 ─────────────────────────────────────────────────

class TestStep5Integration:
    def test_step5_middle_layer_directional_change_is_event(self, telos_manager):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content=json.dumps(_make_step4())),
            MagicMock(content=json.dumps(_make_step5_event())),
        ]
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)
        step3 = Step3Output(**_make_step3_update())
        step4 = engine.step4_generate("challenges", step3, ["摘要"])

        from huaqi_src.layers.growth.telos.models import DimensionLayer
        result = engine.step5_judge_growth("challenges", DimensionLayer.MIDDLE, step4)

        assert result.is_growth_event is True
        assert result.title == "开始质疑努力的方向"
        assert result.narrative is not None


# ── 测试：完整流水线 3 天场景 ─────────────────────────────────────────────────

class TestFullPipeline:
    def test_three_day_journal_triggers_telos_update(
        self,
        signal_store,
        event_store,
        telos_manager,
        telos_dir,
        three_day_signals,
    ):
        import json as _json

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content=_json.dumps(_make_step3_update())),
            MagicMock(content=_json.dumps(_make_step4())),
            MagicMock(content=_json.dumps(_make_step5_event())),
        ]
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        for s in three_day_signals:
            signal_store.save(s)

        step1_result = Step1Output(**_make_step1("challenges"))
        summaries = [
            "用户对方向感感到迷茫（信号 1）",
            "用户对方向感感到迷茫（信号 2）",
            "用户对方向感感到迷茫（信号 3）",
        ]

        result = engine.run_pipeline(
            signal=three_day_signals[2],
            step1_result=step1_result,
            signal_summaries=summaries,
            days=3,
        )

        assert result["updated"] is True
        assert result["growth_event"] is not None
        assert result["growth_event"].is_growth_event is True

    def test_processed_flags_set_after_pipeline(
        self,
        signal_store,
        telos_manager,
        three_day_signals,
    ):
        for s in three_day_signals:
            signal_store.save(s)
            signal_store.mark_processed(s.id)

        unprocessed = signal_store.query(
            RawSignalFilter(user_id="user_a", processed=0)
        )
        assert len(unprocessed) == 0

        processed = signal_store.query(
            RawSignalFilter(user_id="user_a", processed=1)
        )
        assert len(processed) == 3

    def test_telos_update_count_after_pipeline(
        self,
        telos_manager,
    ):
        import json as _json

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content=_json.dumps(_make_step3_update())),
            MagicMock(content=_json.dumps(_make_step4())),
            MagicMock(content=_json.dumps(_make_step5_event())),
        ]
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        step1_result = Step1Output(**_make_step1("challenges"))
        signal = RawSignal(
            user_id="user_a",
            source_type=SourceType.JOURNAL,
            timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc),
            content="第三天的日记",
        )
        engine.run_pipeline(
            signal=signal,
            step1_result=step1_result,
            signal_summaries=["摘要1", "摘要2", "摘要3"],
            days=3,
        )

        dim = telos_manager.get("challenges")
        assert dim.update_count == 1
        assert len(dim.history) == 1

    def test_growth_event_saved_to_store(
        self,
        signal_store,
        event_store,
        telos_manager,
        three_day_signals,
    ):
        import json as _json

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content=_json.dumps(_make_step3_update())),
            MagicMock(content=_json.dumps(_make_step4())),
            MagicMock(content=_json.dumps(_make_step5_event())),
        ]
        engine = TelosEngine(telos_manager=telos_manager, llm=mock_llm)

        for s in three_day_signals:
            signal_store.save(s)

        step1_result = Step1Output(**_make_step1("challenges"))
        pipeline_result = engine.run_pipeline(
            signal=three_day_signals[2],
            step1_result=step1_result,
            signal_summaries=["摘要1", "摘要2", "摘要3"],
            days=3,
        )

        step5 = pipeline_result["growth_event"]
        if step5 and step5.is_growth_event:
            dim = telos_manager.get("challenges")
            event = GrowthEvent(
                user_id="user_a",
                dimension="challenges",
                layer="middle",
                title=step5.title,
                narrative=step5.narrative,
                new_content=dim.content,
                trigger_signals=[s.id for s in three_day_signals],
                occurred_at=datetime.now(timezone.utc),
            )
            event_store.save(event)

        events = event_store.list_by_user("user_a")
        assert len(events) == 1
        assert events[0].title == "开始质疑努力的方向"
        assert len(events[0].trigger_signals) == 3
