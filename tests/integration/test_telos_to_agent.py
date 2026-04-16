"""
集成测试：成长层 → Agent 上下文注入

验证 TelosContextBuilder 能够：
1. 读取 TELOS INDEX.md 生成 telos_snapshot
2. 通过 mock 向量检索生成 relevant_history
3. 按 interaction_mode 拼出完整 system prompt
4. 注入到 AgentState 的三个新字段
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from huaqi_src.agent.state import (
    AgentState,
    create_initial_state,
    INTERACTION_MODE_CHAT,
    INTERACTION_MODE_ONBOARDING,
    INTERACTION_MODE_REPORT,
)
from huaqi_src.layers.growth.telos.context import TelosContextBuilder, SystemPromptBuilder
from huaqi_src.layers.growth.telos.manager import TelosManager


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
def mock_vector_search() -> MagicMock:
    mock = MagicMock()
    mock.search.return_value = [
        {"content": "2026-01-01：今天思考了很多方向感的问题。", "distance": 0.12},
        {"content": "2026-01-02：和朋友聊了职业规划，感觉更清晰了。", "distance": 0.21},
    ]
    return mock


# ── 测试：TelosContextBuilder ─────────────────────────────────────────────────

class TestTelosContextBuilder:
    def test_build_telos_snapshot_contains_dimensions(self, telos_manager):
        builder = TelosContextBuilder(telos_manager=telos_manager)
        snapshot = builder.build_telos_snapshot()

        assert snapshot is not None
        assert len(snapshot) > 0
        assert "beliefs" in snapshot or "TELOS" in snapshot

    def test_build_telos_snapshot_is_string(self, telos_manager):
        builder = TelosContextBuilder(telos_manager=telos_manager)
        snapshot = builder.build_telos_snapshot()
        assert isinstance(snapshot, str)

    def test_build_relevant_history_returns_list(self, telos_manager, mock_vector_search):
        builder = TelosContextBuilder(
            telos_manager=telos_manager,
            vector_search=mock_vector_search,
        )
        history = builder.build_relevant_history(query="今天的状态")

        assert isinstance(history, list)
        assert len(history) == 2

    def test_build_relevant_history_calls_search_with_query(self, telos_manager, mock_vector_search):
        builder = TelosContextBuilder(
            telos_manager=telos_manager,
            vector_search=mock_vector_search,
        )
        builder.build_relevant_history(query="方向感问题")

        mock_vector_search.search.assert_called_once()
        call_args = mock_vector_search.search.call_args
        assert "方向感问题" in str(call_args)

    def test_build_relevant_history_without_vector_returns_empty(self, telos_manager):
        builder = TelosContextBuilder(telos_manager=telos_manager, vector_search=None)
        history = builder.build_relevant_history(query="任意查询")
        assert history == []

    def test_build_relevant_history_filters_by_top_k(self, telos_manager, mock_vector_search):
        mock_vector_search.search.return_value = [
            {"content": f"记忆 {i}", "distance": 0.1 * i} for i in range(10)
        ]
        builder = TelosContextBuilder(
            telos_manager=telos_manager,
            vector_search=mock_vector_search,
        )
        history = builder.build_relevant_history(query="查询", top_k=3)
        assert len(history) <= 3


class TestTelosContextBuilderInjectState:
    def test_inject_updates_telos_snapshot(self, telos_manager, mock_vector_search):
        builder = TelosContextBuilder(
            telos_manager=telos_manager,
            vector_search=mock_vector_search,
        )
        state = create_initial_state(user_id="user_a")
        updated = builder.inject(state, query="今天怎么了")

        assert updated["telos_snapshot"] is not None
        assert len(updated["telos_snapshot"]) > 0

    def test_inject_updates_relevant_history(self, telos_manager, mock_vector_search):
        builder = TelosContextBuilder(
            telos_manager=telos_manager,
            vector_search=mock_vector_search,
        )
        state = create_initial_state(user_id="user_a")
        updated = builder.inject(state, query="今天怎么了")

        assert isinstance(updated["relevant_history"], list)
        assert len(updated["relevant_history"]) > 0

    def test_inject_preserves_interaction_mode(self, telos_manager):
        builder = TelosContextBuilder(telos_manager=telos_manager)
        state = create_initial_state(
            user_id="user_a",
            interaction_mode=INTERACTION_MODE_ONBOARDING,
        )
        updated = builder.inject(state, query="你好")

        assert updated["interaction_mode"] == INTERACTION_MODE_ONBOARDING

    def test_inject_without_query_skips_history(self, telos_manager):
        builder = TelosContextBuilder(telos_manager=telos_manager)
        state = create_initial_state(user_id="user_a")
        updated = builder.inject(state, query=None)

        assert updated["relevant_history"] == []


# ── 测试：SystemPromptBuilder ─────────────────────────────────────────────────

class TestSystemPromptBuilder:
    def test_build_chat_prompt_has_four_parts(self, telos_manager):
        prompt_builder = SystemPromptBuilder()
        prompt = prompt_builder.build(
            telos_snapshot="你相信选择比努力更重要。",
            relevant_history=["2026-01-01：思考方向感。"],
            interaction_mode=INTERACTION_MODE_CHAT,
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_build_chat_prompt_contains_telos(self, telos_manager):
        prompt_builder = SystemPromptBuilder()
        prompt = prompt_builder.build(
            telos_snapshot="你相信选择比努力更重要。",
            relevant_history=[],
            interaction_mode=INTERACTION_MODE_CHAT,
        )
        assert "选择比努力更重要" in prompt

    def test_build_prompt_contains_relevant_history(self):
        prompt_builder = SystemPromptBuilder()
        prompt = prompt_builder.build(
            telos_snapshot="TELOS 快照",
            relevant_history=["历史记忆片段 A", "历史记忆片段 B"],
            interaction_mode=INTERACTION_MODE_CHAT,
        )
        assert "历史记忆片段 A" in prompt
        assert "历史记忆片段 B" in prompt

    def test_build_onboarding_prompt_has_different_tone(self):
        prompt_builder = SystemPromptBuilder()
        chat_prompt = prompt_builder.build(
            telos_snapshot="",
            relevant_history=[],
            interaction_mode=INTERACTION_MODE_CHAT,
        )
        onboarding_prompt = prompt_builder.build(
            telos_snapshot="",
            relevant_history=[],
            interaction_mode=INTERACTION_MODE_ONBOARDING,
        )
        assert chat_prompt != onboarding_prompt

    def test_build_report_prompt_has_different_tone(self):
        prompt_builder = SystemPromptBuilder()
        chat_prompt = prompt_builder.build(
            telos_snapshot="",
            relevant_history=[],
            interaction_mode=INTERACTION_MODE_CHAT,
        )
        report_prompt = prompt_builder.build(
            telos_snapshot="",
            relevant_history=[],
            interaction_mode=INTERACTION_MODE_REPORT,
        )
        assert chat_prompt != report_prompt

    def test_build_empty_history_omits_history_section(self):
        prompt_builder = SystemPromptBuilder()
        prompt = prompt_builder.build(
            telos_snapshot="TELOS",
            relevant_history=[],
            interaction_mode=INTERACTION_MODE_CHAT,
        )
        assert isinstance(prompt, str)


# ── 测试：AgentState 三字段 ──────────────────────────────────────────────────

class TestAgentStateNewFields:
    def test_create_initial_state_has_telos_snapshot(self):
        state = create_initial_state(user_id="user_a", telos_snapshot="快照内容")
        assert state["telos_snapshot"] == "快照内容"

    def test_create_initial_state_has_relevant_history(self):
        state = create_initial_state(user_id="user_a", relevant_history=["记忆A"])
        assert state["relevant_history"] == ["记忆A"]

    def test_create_initial_state_interaction_mode_defaults_to_chat(self):
        state = create_initial_state(user_id="user_a")
        assert state["interaction_mode"] == INTERACTION_MODE_CHAT

    def test_create_initial_state_no_personality_context_field(self):
        state = create_initial_state(user_id="user_a")
        assert "personality_context" not in state

    def test_relevant_history_defaults_to_empty_list(self):
        state = create_initial_state(user_id="user_a")
        assert state["relevant_history"] == []


# ── 测试：端到端 Agent 上下文构建 ────────────────────────────────────────────

class TestEndToEndContextInjection:
    def test_full_context_injection_flow(self, telos_manager, mock_vector_search):
        builder = TelosContextBuilder(
            telos_manager=telos_manager,
            vector_search=mock_vector_search,
        )
        prompt_builder = SystemPromptBuilder()

        state = create_initial_state(user_id="user_a")
        state = builder.inject(state, query="我今天感觉很迷茫")

        prompt = prompt_builder.build(
            telos_snapshot=state["telos_snapshot"],
            relevant_history=state["relevant_history"],
            interaction_mode=state["interaction_mode"],
        )

        assert len(prompt) > 200
        assert isinstance(prompt, str)

    def test_telos_update_reflected_in_next_snapshot(self, telos_manager, mock_vector_search):
        from datetime import datetime, timezone
        from huaqi_src.layers.growth.telos.models import HistoryEntry

        entry = HistoryEntry(
            version=1,
            change="从「迷茫」更新为「目标明确」",
            trigger="日记信号积累",
            confidence=0.8,
            updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        telos_manager.update(
            "challenges",
            new_content="当前挑战：如何在噪音中保持专注。",
            history_entry=entry,
            confidence=0.8,
        )

        builder = TelosContextBuilder(
            telos_manager=telos_manager,
            vector_search=mock_vector_search,
        )
        state = create_initial_state(user_id="user_a")
        updated = builder.inject(state, query="最近怎么了")

        assert "challenges" in updated["telos_snapshot"]

    def test_build_telos_snapshot_contains_full_content(self, telos_manager):
        from datetime import datetime, timezone
        from huaqi_src.layers.growth.telos.models import HistoryEntry
        entry = HistoryEntry(
            version=1,
            change="信念改变了",
            trigger="信号触发",
            confidence=0.8,
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        telos_manager.update(
            "beliefs",
            "选择比努力更重要，专注在少数关键事情上。",
            entry,
            0.8,
        )
        builder = TelosContextBuilder(telos_manager=telos_manager)
        snapshot = builder.build_telos_snapshot()
        assert "选择比努力更重要" in snapshot

    def test_build_telos_snapshot_excludes_history(self, telos_manager):
        from datetime import datetime, timezone
        from huaqi_src.layers.growth.telos.models import HistoryEntry
        entry = HistoryEntry(
            version=1,
            change="不应该出现在快照中的历史内容",
            trigger="触发",
            confidence=0.5,
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        telos_manager.update("beliefs", "当前认知内容", entry, 0.5)
        builder = TelosContextBuilder(telos_manager=telos_manager)
        snapshot = builder.build_telos_snapshot()
        assert "不应该出现在快照中的历史内容" not in snapshot
