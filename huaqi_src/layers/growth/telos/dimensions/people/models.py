import datetime
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class InteractionLog:
    date: str
    signal_id: str
    interaction_type: str
    summary: str


@dataclass
class EmotionalTimeline:
    date: str
    score: float
    trigger: str


@dataclass
class Person:
    person_id: str
    name: str
    relation_type: str
    alias: list[str] = field(default_factory=list)
    profile: str = ""
    emotional_impact: str = "中性"
    interaction_frequency: int = 0
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    interaction_logs: List[InteractionLog] = field(default_factory=list)
    emotional_timeline: List[EmotionalTimeline] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "person_id": self.person_id,
            "name": self.name,
            "relation_type": self.relation_type,
            "alias": self.alias,
            "profile": self.profile,
            "emotional_impact": self.emotional_impact,
            "interaction_frequency": self.interaction_frequency,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "interaction_logs": [
                {
                    "date": l.date,
                    "signal_id": l.signal_id,
                    "interaction_type": l.interaction_type,
                    "summary": l.summary,
                }
                for l in self.interaction_logs
            ],
            "emotional_timeline": [
                {
                    "date": e.date,
                    "score": e.score,
                    "trigger": e.trigger,
                }
                for e in self.emotional_timeline
            ],
        }


@dataclass
class Relation:
    from_person_id: str
    to_person_id: str
    relation_strength: int = 50
    topics: list[str] = field(default_factory=list)
    history_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_person_id": self.from_person_id,
            "to_person_id": self.to_person_id,
            "relation_strength": self.relation_strength,
            "topics": self.topics,
            "history_summary": self.history_summary,
        }
