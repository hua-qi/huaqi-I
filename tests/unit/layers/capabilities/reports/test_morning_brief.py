import pytest
from pathlib import Path
from unittest.mock import patch
from huaqi_src.layers.capabilities.reports.morning_brief import MorningBriefAgent


def test_morning_brief_creates_report_file(tmp_path):
    agent = MorningBriefAgent(data_dir=tmp_path)

    fake_llm_response = "今日简报：保持专注，世界很精彩。"
    with patch.object(agent, "_generate_brief", return_value=fake_llm_response):
        agent.run()

    report_dir = tmp_path / "reports" / "daily"
    files = list(report_dir.glob("*-morning.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "今日简报" in content


def test_morning_brief_collects_world_news_context(tmp_path):
    import datetime
    from huaqi_src.layers.data.world.storage import WorldNewsStorage
    from huaqi_src.layers.data.collectors.document import HuaqiDocument

    storage = WorldNewsStorage(data_dir=tmp_path)
    storage.save(
        [HuaqiDocument(
            doc_id="w-001",
            doc_type="world_news",
            source="rss:test",
            content="Python 3.14 正式发布",
            timestamp=datetime.datetime.now(),
        )],
        date=datetime.date.today(),
    )

    agent = MorningBriefAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "Python 3.14" in context or "world" in context.lower() or "新闻" in context


def test_morning_brief_context_includes_people(tmp_path):
    from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph
    from huaqi_src.layers.growth.telos.dimensions.people.models import Person

    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="p1",
        name="张三",
        relation_type="同事",
        interaction_frequency=8,
    ))

    agent = MorningBriefAgent(data_dir=tmp_path)
    context = agent._build_context()
    assert "张三" in context
