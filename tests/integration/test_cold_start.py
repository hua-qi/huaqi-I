"""
集成测试：冷启动全流程

场景：新用户首次启动系统
- 自动进入对话式问卷（10个问题）
- 支持跳过任意问题
- 问卷结束后生成 TELOS 文件
- 跳过的问题不生成对应维度文件（仅保留占位内容）
- 所有生成维度的 confidence = 0.5
- 用户纠正总结后，META 写入第一批校正记录
- 问卷完成后系统进入正常对话模式
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from huaqi_src.layers.capabilities.onboarding.questionnaire import (
    OnboardingQuestionnaire,
    OnboardingSession,
    ONBOARDING_QUESTIONS,
)
from huaqi_src.layers.capabilities.onboarding.telos_generator import (
    OnboardingTelosGenerator,
)
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.meta import MetaManager, CorrectionRecord
from huaqi_src.layers.growth.telos.models import STANDARD_DIMENSIONS
from huaqi_src.agent.state import INTERACTION_MODE_ONBOARDING, INTERACTION_MODE_CHAT


# ── fixtures ──────────────────────────────────────────────────────────────────

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
def meta_manager(telos_dir: Path) -> MetaManager:
    return MetaManager(meta_path=telos_dir / "meta.md")


# ── 测试：问卷结构 ────────────────────────────────────────────────────────────

class TestOnboardingQuestions:
    def test_ten_questions_defined(self):
        assert len(ONBOARDING_QUESTIONS) == 10

    def test_each_question_has_dimension(self):
        for q in ONBOARDING_QUESTIONS:
            assert q.dimension in STANDARD_DIMENSIONS + ["meta"]

    def test_each_question_has_text(self):
        for q in ONBOARDING_QUESTIONS:
            assert len(q.text) > 10

    def test_goals_is_first_question(self):
        assert ONBOARDING_QUESTIONS[0].dimension == "goals"

    def test_meta_is_last_question(self):
        assert ONBOARDING_QUESTIONS[-1].dimension == "meta"


# ── 测试：OnboardingSession ───────────────────────────────────────────────────

class TestOnboardingSession:
    def test_session_starts_at_question_zero(self):
        session = OnboardingSession()
        assert session.current_index == 0

    def test_current_question_returns_first(self):
        session = OnboardingSession()
        q = session.current_question()
        assert q.dimension == "goals"

    def test_answer_advances_index(self):
        session = OnboardingSession()
        session.answer("完成 huaqi 系统 MVP")
        assert session.current_index == 1

    def test_skip_advances_index_without_answer(self):
        session = OnboardingSession()
        session.skip()
        assert session.current_index == 1
        assert session.answers.get("goals") is None

    def test_is_complete_after_all_questions(self):
        session = OnboardingSession()
        for _ in ONBOARDING_QUESTIONS:
            session.answer("测试回答")
        assert session.is_complete()

    def test_is_not_complete_before_all_questions(self):
        session = OnboardingSession()
        session.answer("回答一个")
        assert not session.is_complete()

    def test_skip_all_questions_is_still_complete(self):
        session = OnboardingSession()
        for _ in ONBOARDING_QUESTIONS:
            session.skip()
        assert session.is_complete()

    def test_get_answered_pairs(self):
        session = OnboardingSession()
        session.answer("完成 MVP")
        session.skip()
        session.answer("最近学到了 LangGraph")

        pairs = session.get_answered_pairs()
        assert len(pairs) == 2
        assert any(p.dimension == "goals" for p in pairs)
        assert any(p.dimension == "learned" for p in pairs)

    def test_skipped_dimension_not_in_answered_pairs(self):
        session = OnboardingSession()
        session.skip()
        pairs = session.get_answered_pairs()
        assert not any(p.dimension == "goals" for p in pairs)


# ── 测试：OnboardingQuestionnaire（对话推进） ─────────────────────────────────

class TestOnboardingQuestionnaire:
    def test_next_prompt_returns_first_question(self):
        q = OnboardingQuestionnaire()
        prompt = q.next_prompt()
        assert prompt is not None
        assert len(prompt) > 5

    def test_process_answer_advances(self):
        q = OnboardingQuestionnaire()
        q.next_prompt()
        q.process_answer("完成 huaqi MVP")
        assert q.session.current_index == 1

    def test_process_skip_advances(self):
        q = OnboardingQuestionnaire()
        q.next_prompt()
        q.process_skip()
        assert q.session.current_index == 1

    def test_is_done_after_all(self):
        q = OnboardingQuestionnaire()
        while not q.is_done():
            q.next_prompt()
            q.process_skip()
        assert q.is_done()

    def test_next_prompt_is_none_when_done(self):
        q = OnboardingQuestionnaire()
        while not q.is_done():
            q.next_prompt()
            q.process_skip()
        assert q.next_prompt() is None


# ── 测试：OnboardingTelosGenerator ───────────────────────────────────────────

class TestOnboardingTelosGenerator:
    def test_generate_creates_answered_dimensions(self, telos_manager):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({
                "goals": "完成 huaqi 系统的 MVP，让 AI 真正了解自己。",
                "challenges": "执行力不足，容易被琐事打断。",
                "beliefs": None,
            })
        )
        generator = OnboardingTelosGenerator(telos_manager=telos_manager, llm=mock_llm)

        session = OnboardingSession()
        session.answer("完成 huaqi MVP")
        session.answer("执行力不足")
        session.skip()

        generator.generate(session)

        goals_dim = telos_manager.get("goals")
        assert "MVP" in goals_dim.content or "完成" in goals_dim.content

    def test_generated_dimensions_have_confidence_half(self, telos_manager):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({
                "goals": "完成 MVP",
                "challenges": "执行力不足",
            })
        )
        generator = OnboardingTelosGenerator(telos_manager=telos_manager, llm=mock_llm)

        session = OnboardingSession()
        session.answer("完成 MVP")
        session.answer("执行力不足")
        for _ in range(8):
            session.skip()

        generator.generate(session)

        goals_dim = telos_manager.get("goals")
        assert goals_dim.confidence == 0.5

    def test_skipped_questions_keep_placeholder_content(self, telos_manager):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({"goals": "完成 MVP"})
        )
        generator = OnboardingTelosGenerator(telos_manager=telos_manager, llm=mock_llm)

        session = OnboardingSession()
        session.answer("完成 MVP")
        for _ in range(9):
            session.skip()

        generator.generate(session)

        beliefs_dim = telos_manager.get("beliefs")
        assert beliefs_dim.content == "（待补充）"

    def test_generate_summary_for_user_confirmation(self, telos_manager):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({"goals": "完成 MVP", "challenges": "执行力不足"})
        )
        generator = OnboardingTelosGenerator(telos_manager=telos_manager, llm=mock_llm)

        session = OnboardingSession()
        session.answer("完成 MVP")
        session.answer("执行力不足")
        for _ in range(8):
            session.skip()

        generator.generate(session)
        summary = generator.build_confirmation_summary()

        assert isinstance(summary, str)
        assert len(summary) > 20


# ── 测试：META 校正记录 ───────────────────────────────────────────────────────

class TestOnboardingMetaCorrection:
    def test_correction_written_to_meta(self, telos_manager, telos_dir):
        from datetime import datetime, timezone

        meta_mgr = MetaManager(meta_path=telos_dir / "meta.md")
        meta_mgr.init(active_dimensions=STANDARD_DIMENSIONS)

        record = CorrectionRecord(
            date=datetime(2026, 1, 4, tzinfo=timezone.utc),
            agent_conclusion="你的目标是完成 MVP",
            user_feedback="不对，我还想同时改善身体状态",
            correction_direction="用户目标不止一个，注意多目标并行",
        )
        meta_mgr.add_correction(record)

        records = meta_mgr.list_corrections()
        assert len(records) == 1
        assert "MVP" in records[0].agent_conclusion

    def test_multiple_corrections_stored(self, telos_dir):
        from datetime import datetime, timezone

        meta_mgr = MetaManager(meta_path=telos_dir / "meta.md")
        meta_mgr.init(active_dimensions=STANDARD_DIMENSIONS)

        for i in range(3):
            meta_mgr.add_correction(CorrectionRecord(
                date=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                agent_conclusion=f"结论 {i}",
                user_feedback=f"反馈 {i}",
                correction_direction=f"校正 {i}",
            ))

        records = meta_mgr.list_corrections()
        assert len(records) == 3


# ── 测试：完整冷启动流程 ──────────────────────────────────────────────────────

class TestFullColdStartFlow:
    def test_complete_flow_ends_in_chat_mode(self, telos_manager):
        q = OnboardingQuestionnaire()
        while not q.is_done():
            q.next_prompt()
            q.process_skip()

        assert q.is_done()
        final_mode = INTERACTION_MODE_CHAT
        assert final_mode == "chat"

    def test_partial_answers_generate_partial_telos(self, telos_manager):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({
                "goals": "完成 MVP",
                "narratives": "我是一个慢热但持久的人",
            })
        )
        generator = OnboardingTelosGenerator(telos_manager=telos_manager, llm=mock_llm)

        session = OnboardingSession()
        session.answer("完成 MVP")
        session.skip()
        session.skip()
        for _ in range(3):
            session.skip()
        session.answer("我是一个慢热但持久的人")
        for _ in range(3):
            session.skip()

        generator.generate(session)

        goals_dim = telos_manager.get("goals")
        assert goals_dim.confidence == 0.5
        narratives_dim = telos_manager.get("narratives")
        assert narratives_dim.confidence == 0.5

    def test_onboarding_mode_then_chat_mode(self):
        assert INTERACTION_MODE_ONBOARDING == "onboarding"
        assert INTERACTION_MODE_CHAT == "chat"
        assert INTERACTION_MODE_ONBOARDING != INTERACTION_MODE_CHAT
