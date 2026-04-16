import datetime
from huaqi_src.layers.growth.telos.dimensions.people.models import (
    InteractionLog,
    EmotionalTimeline,
    Person,
)


def test_interaction_log_fields():
    log = InteractionLog(
        date="2026-10-01",
        signal_id="sig_abc123",
        interaction_type="合作",
        summary="一起推进了产品评审",
    )
    assert log.date == "2026-10-01"
    assert log.interaction_type == "合作"


def test_emotional_timeline_fields():
    entry = EmotionalTimeline(
        date="2026-10-01",
        score=0.7,
        trigger="合作顺畅",
    )
    assert entry.score == 0.7


def test_person_has_interaction_logs_field():
    person = Person(
        person_id="p1",
        name="张伟",
        relation_type="同事",
    )
    assert person.interaction_logs == []
    assert person.emotional_timeline == []


def test_person_accepts_interaction_logs():
    log = InteractionLog(
        date="2026-10-01",
        signal_id="sig_1",
        interaction_type="日常",
        summary="日常交流",
    )
    person = Person(
        person_id="p1",
        name="张伟",
        relation_type="同事",
        interaction_logs=[log],
    )
    assert len(person.interaction_logs) == 1
