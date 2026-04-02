import datetime
from huaqi_src.layers.growth.telos.dimensions.people.models import Person, Relation


def test_person_creation():
    p = Person(
        person_id="zhangsan-001",
        name="张三",
        relation_type="同事",
    )
    assert p.person_id == "zhangsan-001"
    assert p.name == "张三"
    assert p.alias == []
    assert p.profile == ""
    assert p.emotional_impact == "中性"
    assert p.interaction_frequency == 0
    assert p.notes == ""


def test_person_to_dict():
    p = Person(
        person_id="lisi-001",
        name="李四",
        relation_type="朋友",
        alias=["小李"],
        profile="直接说结论，技术能力强",
        emotional_impact="积极",
        interaction_frequency=5,
    )
    d = p.to_dict()
    assert d["name"] == "李四"
    assert d["alias"] == ["小李"]
    assert d["emotional_impact"] == "积极"


def test_relation_creation():
    r = Relation(
        from_person_id="me",
        to_person_id="zhangsan-001",
        relation_strength=75,
        topics=["技术", "项目"],
        history_summary="认识3年，合作密切",
    )
    assert r.relation_strength == 75
    assert "技术" in r.topics


def test_relation_to_dict():
    r = Relation(
        from_person_id="me",
        to_person_id="lisi-001",
        relation_strength=50,
    )
    d = r.to_dict()
    assert d["from_person_id"] == "me"
    assert d["relation_strength"] == 50
