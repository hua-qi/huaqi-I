import datetime
import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.reports.quarterly_report import QuarterlyReportAgent


def test_quarterly_report_creates_file(tmp_path):
    agent = QuarterlyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="本季度成长总结"):
        agent.run()
    report_dir = tmp_path / "reports" / "quarterly"
    files = list(report_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "成长总结" in content


def test_quarterly_report_filename_format(tmp_path):
    agent = QuarterlyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="季报"):
        agent.run()
    report_dir = tmp_path / "reports" / "quarterly"
    files = list(report_dir.glob("*.md"))
    assert len(files) == 1
    today = datetime.date.today()
    quarter = (today.month - 1) // 3 + 1
    expected = f"{today.year}-Q{quarter}"
    assert expected in files[0].name


def test_quarterly_report_context_includes_weekly_reports(tmp_path):
    weekly_dir = tmp_path / "reports" / "weekly"
    weekly_dir.mkdir(parents=True)
    (weekly_dir / "2026-W10.md").write_text("本周完成了架构设计", encoding="utf-8")
    (weekly_dir / "2026-W11.md").write_text("本周完成了功能开发", encoding="utf-8")

    agent = QuarterlyReportAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "架构设计" in context or "W10" in context
