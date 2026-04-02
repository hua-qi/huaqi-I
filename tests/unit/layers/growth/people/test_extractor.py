import pytest
from unittest.mock import patch, MagicMock
from huaqi_src.layers.growth.telos.dimensions.people.extractor import PersonExtractor
from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph


def test_extract_from_text_returns_list(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    extractor = PersonExtractor(graph=graph)

    fake_llm_output = """[
      {
        "name": "张三",
        "relation_type": "同事",
        "profile": "技术负责人，逻辑清晰",
        "emotional_impact": "积极",
        "alias": []
      }
    ]"""

    with patch.object(extractor, "_call_llm", return_value=fake_llm_output):
        extracted = extractor.extract_from_text(
            "今天和张三开了个项目会议，他是技术负责人，表现很好"
        )

    assert len(extracted) == 1
    assert extracted[0].name == "张三"
    assert extracted[0].relation_type == "同事"


def test_extract_saves_to_graph(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    extractor = PersonExtractor(graph=graph)

    fake_llm_output = """[
      {
        "name": "李四",
        "relation_type": "朋友",
        "profile": "设计师",
        "emotional_impact": "中性",
        "alias": ["小李"]
      }
    ]"""

    with patch.object(extractor, "_call_llm", return_value=fake_llm_output):
        extractor.extract_from_text("和李四吃饭，他是设计师")

    person = graph.get_person("李四")
    assert person is not None
    assert "设计师" in person.profile


def test_extract_merges_existing_person(tmp_path):
    from huaqi_src.layers.growth.telos.dimensions.people.models import Person
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="zhangsan-001",
        name="张三",
        relation_type="同事",
        profile="Python 专家",
        interaction_frequency=3,
    ))

    extractor = PersonExtractor(graph=graph)
    fake_llm_output = """[
      {
        "name": "张三",
        "relation_type": "同事",
        "profile": "Python 专家，喜欢开源",
        "emotional_impact": "积极",
        "alias": []
      }
    ]"""

    with patch.object(extractor, "_call_llm", return_value=fake_llm_output):
        extractor.extract_from_text("张三今天分享了一个开源项目")

    person = graph.get_person("张三")
    assert person.interaction_frequency == 4


def test_extract_handles_invalid_llm_output(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    extractor = PersonExtractor(graph=graph)

    with patch.object(extractor, "_call_llm", return_value="这不是JSON"):
        result = extractor.extract_from_text("随意的文本")

    assert result == []
