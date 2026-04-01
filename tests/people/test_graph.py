import datetime
import pytest
from huaqi_src.people.graph import PeopleGraph
from huaqi_src.people.models import Person, Relation


def test_add_and_get_person(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    person = Person(
        person_id="zhangsan-001",
        name="张三",
        relation_type="同事",
        profile="喜欢直接说结论",
    )
    graph.add_person(person)
    result = graph.get_person("张三")
    assert result is not None
    assert result.name == "张三"
    assert result.profile == "喜欢直接说结论"


def test_add_person_creates_markdown_file(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    person = Person(person_id="lisi-001", name="李四", relation_type="朋友")
    graph.add_person(person)
    md_file = tmp_path / "people" / "李四.md"
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "李四" in content
    assert "朋友" in content


def test_list_people(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(person_id="p1", name="张三", relation_type="同事"))
    graph.add_person(Person(person_id="p2", name="李四", relation_type="朋友"))
    people = graph.list_people()
    names = [p.name for p in people]
    assert "张三" in names
    assert "李四" in names


def test_update_person(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    person = Person(person_id="p1", name="张三", relation_type="同事", notes="")
    graph.add_person(person)
    graph.update_person("张三", notes="喜欢喝咖啡", interaction_frequency=10)
    updated = graph.get_person("张三")
    assert updated.notes == "喜欢喝咖啡"
    assert updated.interaction_frequency == 10


def test_delete_person(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(person_id="p1", name="张三", relation_type="同事"))
    graph.delete_person("张三")
    assert graph.get_person("张三") is None
    assert not (tmp_path / "people" / "张三.md").exists()


def test_search_person(tmp_path):
    graph = PeopleGraph(data_dir=tmp_path)
    graph.add_person(Person(
        person_id="p1", name="张三", relation_type="同事",
        profile="Python 专家，喜欢开源"
    ))
    graph.add_person(Person(
        person_id="p2", name="李四", relation_type="朋友",
        profile="设计师，喜欢摄影"
    ))
    results = graph.search("Python")
    assert len(results) >= 1
    assert results[0].name == "张三"
