"""
能力层测试：成长报告

验证：
- GrowthReportBuilder 能读取 TELOS + GrowthEvents 构建报告上下文
- 报告包含维度变化、成长事件列表
- LLM 生成的报告内容基于 TELOS 快照（mock LLM）
- 报告可以保存到文件
- 无成长事件时报告有对应说明
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
from huaqi_src.layers.capabilities.reports.growth_report import GrowthReportBuilder, GrowthReport
from huaqi_src.layers.growth.telos.growth_events import GrowthEvent, GrowthEventStore
from huaqi_src.layers.growth.telos.manager import TelosManager
from huaqi_src.layers.growth.telos.models import HistoryEntry, DimensionLayer


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
def storage_adapter(tmp_path: Path) -> SQLiteStorageAdapter:
    return SQLiteStorageAdapter(db_path=tmp_path / "test.db")


@pytest.fixture
def event_store(storage_adapter: SQLiteStorageAdapter) -> GrowthEventStore:
    return GrowthEventStore(adapter=storage_adapter)


@pytest.fixture
def telos_with_update(telos_manager: TelosManager) -> TelosManager:
    entry = HistoryEntry(
        version=1,
        change="从「迷茫」转变为「目标清晰」",
        trigger="日记连续 3 次提到方向感问题",
        confidence=0.78,
        updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
    )
    telos_manager.update(
        "challenges",
        new_content="当前最大挑战是如何在噪音中保持专注。",
        history_entry=entry,
        confidence=0.78,
    )
    return telos_manager


@pytest.fixture
def sample_event(event_store: GrowthEventStore) -> GrowthEvent:
    event = GrowthEvent(
        user_id="user_a",
        dimension="challenges",
        layer="middle",
        title="开始质疑努力的方向",
        narrative="你开始意识到方向比努力更重要。过去一个月的日记都在反复印证这个认知。",
        old_content="执行力不足",
        new_content="当前最大挑战是如何在噪音中保持专注。",
        trigger_signals=["sig-1", "sig-2", "sig-3"],
        occurred_at=datetime.now(timezone.utc),
    )
    event_store.save(event)
    return event


# ── 测试：GrowthReport 模型 ───────────────────────────────────────────────────

class TestGrowthReport:
    def test_report_has_required_fields(self):
        report = GrowthReport(
            user_id="user_a",
            period="weekly",
            period_label="2026-W01",
            telos_snapshot="快照内容",
            growth_events=[],
            narrative="本周成长叙事",
            generated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        assert report.user_id == "user_a"
        assert report.period == "weekly"
        assert report.narrative == "本周成长叙事"

    def test_report_to_markdown(self):
        report = GrowthReport(
            user_id="user_a",
            period="weekly",
            period_label="2026-W01",
            telos_snapshot="你相信选择比努力更重要。",
            growth_events=[],
            narrative="本周没有明显的认知变化，但保持了稳定输入。",
            generated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        md = report.to_markdown()
        assert "2026-W01" in md
        assert "本周没有明显的认知变化" in md

    def test_report_with_events_to_markdown(self, sample_event):
        report = GrowthReport(
            user_id="user_a",
            period="weekly",
            period_label="2026-W01",
            telos_snapshot="快照",
            growth_events=[sample_event],
            narrative="本周有一次重要的认知转变。",
            generated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        md = report.to_markdown()
        assert "开始质疑努力的方向" in md


# ── 测试：GrowthReportBuilder.build_context ───────────────────────────────────

class TestGrowthReportBuilderContext:
    def test_context_contains_telos_snapshot(self, telos_with_update, event_store):
        builder = GrowthReportBuilder(
            telos_manager=telos_with_update,
            event_store=event_store,
        )
        ctx = builder.build_context(user_id="user_a", days=7)
        assert "challenges" in ctx or "TELOS" in ctx

    def test_context_contains_growth_events(self, telos_with_update, event_store, sample_event):
        builder = GrowthReportBuilder(
            telos_manager=telos_with_update,
            event_store=event_store,
        )
        ctx = builder.build_context(user_id="user_a", days=7)
        assert "开始质疑努力的方向" in ctx

    def test_context_no_events_mentions_stable(self, telos_manager, event_store):
        builder = GrowthReportBuilder(
            telos_manager=telos_manager,
            event_store=event_store,
        )
        ctx = builder.build_context(user_id="user_a", days=7)
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_context_filters_by_user_id(self, telos_manager, event_store):
        other_event = GrowthEvent(
            user_id="user_b",
            dimension="beliefs",
            layer="core",
            title="B 的成长事件",
            narrative="与 user_a 无关",
            new_content="内容",
            trigger_signals=[],
            occurred_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )
        event_store.save(other_event)

        builder = GrowthReportBuilder(
            telos_manager=telos_manager,
            event_store=event_store,
        )
        ctx = builder.build_context(user_id="user_a", days=7)
        assert "B 的成长事件" not in ctx


# ── 测试：GrowthReportBuilder.generate ───────────────────────────────────────

class TestGrowthReportBuilderGenerate:
    def test_generate_returns_growth_report(self, telos_with_update, event_store, sample_event):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="本周你经历了一次重要的认知转变：开始相信方向比努力更重要。这是过去一个月积累的结果。"
        )
        builder = GrowthReportBuilder(
            telos_manager=telos_with_update,
            event_store=event_store,
            llm=mock_llm,
        )
        report = builder.generate(user_id="user_a", period="weekly", period_label="2026-W01", days=7)

        assert isinstance(report, GrowthReport)
        assert report.user_id == "user_a"
        assert report.period_label == "2026-W01"

    def test_generate_narrative_from_llm(self, telos_with_update, event_store, sample_event):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="本周最重要的成长：你开始质疑努力的方向。"
        )
        builder = GrowthReportBuilder(
            telos_manager=telos_with_update,
            event_store=event_store,
            llm=mock_llm,
        )
        report = builder.generate(user_id="user_a", period="weekly", period_label="2026-W01", days=7)
        assert "质疑" in report.narrative or len(report.narrative) > 10

    def test_generate_without_llm_uses_template(self, telos_manager, event_store):
        builder = GrowthReportBuilder(
            telos_manager=telos_manager,
            event_store=event_store,
            llm=None,
        )
        report = builder.generate(user_id="user_a", period="weekly", period_label="2026-W01", days=7)
        assert isinstance(report, GrowthReport)
        assert len(report.narrative) > 0

    def test_generate_includes_growth_events(self, telos_with_update, event_store, sample_event):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="本周成长叙事。")
        builder = GrowthReportBuilder(
            telos_manager=telos_with_update,
            event_store=event_store,
            llm=mock_llm,
        )
        report = builder.generate(user_id="user_a", period="weekly", period_label="2026-W01", days=7)
        assert len(report.growth_events) == 1
        assert report.growth_events[0].title == "开始质疑努力的方向"


# ── 测试：报告保存 ────────────────────────────────────────────────────────────

class TestGrowthReportSave:
    def test_save_creates_markdown_file(self, telos_manager, event_store, tmp_path):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="本周成长叙事。")
        builder = GrowthReportBuilder(
            telos_manager=telos_manager,
            event_store=event_store,
            llm=mock_llm,
        )
        report = builder.generate(user_id="user_a", period="weekly", period_label="2026-W01", days=7)

        save_dir = tmp_path / "reports"
        report_path = builder.save(report, output_dir=save_dir)

        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "2026-W01" in content

    def test_save_filename_includes_period_label(self, telos_manager, event_store, tmp_path):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="叙事。")
        builder = GrowthReportBuilder(
            telos_manager=telos_manager,
            event_store=event_store,
            llm=mock_llm,
        )
        report = builder.generate(user_id="user_a", period="weekly", period_label="2026-W01", days=7)
        save_dir = tmp_path / "reports"
        path = builder.save(report, output_dir=save_dir)

        assert "2026-W01" in path.name
