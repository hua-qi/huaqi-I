import datetime
import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.reports.weekly_report import WeeklyReportAgent


def test_weekly_report_creates_file(tmp_path):
    agent = WeeklyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="本周成长亮点：完成了 Phase 2"):
        agent.run()
    report_dir = tmp_path / "reports" / "weekly"
    files = list(report_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Phase 2" in content


def test_weekly_report_context_includes_last_7_days_diaries(tmp_path):
    diary_dir = tmp_path / "memory" / "diary"
    diary_dir.mkdir(parents=True)
    for i in range(3):
        date = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        (diary_dir / f"{date}.md").write_text(f"第{i}天的日记内容", encoding="utf-8")

    agent = WeeklyReportAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "第0天" in context
    assert "第1天" in context


def test_weekly_report_iso_week_in_filename(tmp_path):
    agent = WeeklyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="周报"):
        agent.run()
    report_dir = tmp_path / "reports" / "weekly"
    files = list(report_dir.glob("*.md"))
    assert len(files) == 1
    today = datetime.date.today()
    expected_week = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    assert expected_week in files[0].name
