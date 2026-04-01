import datetime
import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.reports.daily_report import DailyReportAgent


def test_daily_report_creates_file(tmp_path):
    agent = DailyReportAgent(data_dir=tmp_path)
    with patch.object(agent, "_generate_report", return_value="今日复盘：收获满满"):
        agent.run()
    report_dir = tmp_path / "reports" / "daily"
    files = list(report_dir.glob("*-evening.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "今日复盘" in content


def test_daily_report_context_includes_diary(tmp_path):
    diary_dir = tmp_path / "memory" / "diary"
    diary_dir.mkdir(parents=True)
    today = datetime.date.today().isoformat()
    (diary_dir / f"{today}.md").write_text("今天完成了 Phase 2 开发", encoding="utf-8")

    agent = DailyReportAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "Phase 2" in context


def test_daily_report_context_includes_people(tmp_path):
    from huaqi_src.people.graph import PeopleGraph
    from huaqi_src.people.models import Person
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="p1", name="张三", relation_type="同事",
        interaction_frequency=5
    ))

    agent = DailyReportAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "张三" in context
