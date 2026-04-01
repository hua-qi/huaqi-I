import datetime
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HuaqiDocument:
    doc_id: str
    doc_type: str
    source: str
    content: str
    timestamp: datetime.datetime
    summary: str = ""
    people: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "people": self.people,
            "metadata": self.metadata,
        }
