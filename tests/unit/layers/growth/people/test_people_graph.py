from pathlib import Path
import pytest
from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph
from huaqi_src.layers.growth.telos.dimensions.people.models import (
    Person,
    InteractionLog,
    EmotionalTimeline,
)


@pytest.fixture
def graph(tmp_path: Path) -> PeopleGraph:
    return PeopleGraph(data_dir=tmp_path)


def test_graph_writes_and_reads_interaction_logs(graph):
    log = InteractionLog(
        date="2026-10-01",
        signal_id="sig_1",
        interaction_type="合作",
        summary="讨论产品方向",
    )
    person = Person(
        person_id="p1",
        name="张伟",
        relation_type="同事",
        interaction_logs=[log],
    )
    graph.add_person(person)

    loaded = graph.get_person("张伟")
    assert loaded is not None
    assert len(loaded.interaction_logs) == 1
    assert loaded.interaction_logs[0].interaction_type == "合作"
    assert loaded.interaction_logs[0].signal_id == "sig_1"


def test_graph_writes_and_reads_emotional_timeline(graph):
    entry = EmotionalTimeline(date="2026-10-01", score=0.7, trigger="合作顺畅")
    person = Person(
        person_id="p1",
        name="李四",
        relation_type="朋友",
        emotional_timeline=[entry],
    )
    graph.add_person(person)

    loaded = graph.get_person("李四")
    assert loaded is not None
    assert len(loaded.emotional_timeline) == 1
    assert abs(loaded.emotional_timeline[0].score - 0.7) < 0.001
    assert loaded.emotional_timeline[0].trigger == "合作顺畅"


def test_graph_truncates_interaction_logs_at_50(graph):
    logs = [
        InteractionLog(date=f"2026-{i:02d}-01", signal_id=f"sig_{i}", interaction_type="日常", summary=f"第{i}次")
        for i in range(1, 60)
    ]
    person = Person(person_id="p1", name="王五", relation_type="同事", interaction_logs=logs)
    graph.add_person(person)

    loaded = graph.get_person("王五")
    assert loaded is not None
    assert len(loaded.interaction_logs) <= 50


def test_graph_archives_overflow_logs(graph, tmp_path):
    logs = [
        InteractionLog(date=f"2026-{(i % 12) + 1:02d}-01", signal_id=f"sig_{i}", interaction_type="日常", summary=f"第{i}次")
        for i in range(1, 60)
    ]
    person = Person(person_id="p1", name="赵六", relation_type="同事", interaction_logs=logs)
    graph.add_person(person)

    archive_dir = tmp_path / "people" / "_archive"
    archive_files = list(archive_dir.glob("赵六_*.md")) if archive_dir.exists() else []
    assert len(archive_files) >= 1


def test_graph_backward_compatible_without_new_sections(graph):
    old_md = """# 旧人物

**关系类型:** 朋友
**情感倾向:** 积极（huaqi 的观察）
**近30天互动次数:** 0

## 画像
暂无

## 备注
暂无

<!-- person_id: old-001 -->
<!-- alias: [] -->
<!-- created_at: 2026-01-01T00:00:00 -->
<!-- updated_at: 2026-01-01T00:00:00 -->
"""
    people_dir = graph._people_dir
    (people_dir / "旧人物.md").write_text(old_md, encoding="utf-8")

    loaded = graph.get_person("旧人物")
    assert loaded is not None
    assert loaded.interaction_logs == []
    assert loaded.emotional_timeline == []


def test_get_top_n_returns_n_people(graph):
    for i in range(5):
        person = Person(
            person_id=f"p{i}",
            name=f"人物{i}",
            relation_type="同事",
            interaction_logs=[
                InteractionLog(date="2026-10-01", signal_id=f"s{i}", interaction_type="日常", summary="日常")
                for _ in range(i + 1)
            ],
            emotional_timeline=[EmotionalTimeline(date="2026-10-01", score=0.1 * (i + 1), trigger="test")],
        )
        graph.add_person(person)

    top = graph.get_top_n(n=3)
    assert len(top) == 3


def test_get_top_n_ranks_by_freq_and_emotion(graph):
    high = Person(
        person_id="ph",
        name="高频人",
        relation_type="同事",
        interaction_logs=[
            InteractionLog(date="2026-10-01", signal_id=f"s{i}", interaction_type="日常", summary="日常")
            for i in range(20)
        ],
        emotional_timeline=[EmotionalTimeline(date="2026-10-01", score=0.9, trigger="强情感")],
    )
    low = Person(
        person_id="pl",
        name="低频人",
        relation_type="同事",
        interaction_logs=[],
        emotional_timeline=[EmotionalTimeline(date="2026-10-01", score=0.1, trigger="弱情感")],
    )
    graph.add_person(high)
    graph.add_person(low)

    top = graph.get_top_n(n=2)
    assert top[0].name == "高频人"


def test_get_top_n_fallback_when_no_emotional_timeline(graph):
    person = Person(
        person_id="p1",
        name="无情感时序人",
        relation_type="同事",
        interaction_logs=[
            InteractionLog(date="2026-10-01", signal_id="s1", interaction_type="日常", summary="日常")
        ],
        emotional_timeline=[],
        emotional_impact="积极",
    )
    graph.add_person(person)

    top = graph.get_top_n(n=1)
    assert len(top) == 1
