from datetime import datetime, timezone, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from huaqi_src.layers.data.raw_signal.models import RawSignal, RawSignalFilter, SourceType
from huaqi_src.layers.data.raw_signal.store import RawSignalStore


class LearningRecord(BaseModel):
    user_id: str
    topic: str
    source: str
    insight: Optional[str] = None
    occurred_at: datetime

    @field_validator("topic")
    @classmethod
    def topic_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("topic must not be empty")
        return v


class LearningProgress(BaseModel):
    total: int
    completed: int
    recent_topics: List[str] = Field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.completed / self.total


class LearningTracker:

    def __init__(self, signal_store: RawSignalStore) -> None:
        self._store = signal_store

    def record(self, record: LearningRecord) -> None:
        parts = [f"学习记录：{record.topic}"]
        if record.insight:
            parts.append(f"洞察：{record.insight}")
        parts.append(f"来源：{record.source}")
        content = "\n".join(parts)

        signal = RawSignal(
            user_id=record.user_id,
            source_type=SourceType.READING,
            timestamp=record.occurred_at,
            content=content,
            metadata={"topic": record.topic, "source": record.source},
        )
        self._store.save(signal)

    def get_progress(self, user_id: str, days: int = 7) -> LearningProgress:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        signals = self._store.query(
            RawSignalFilter(
                user_id=user_id,
                source_type=SourceType.READING,
                since=since,
                limit=200,
            )
        )

        topics: List[str] = []
        for s in signals:
            meta = s.metadata
            if isinstance(meta, dict) and meta.get("topic"):
                topics.append(meta["topic"])

        return LearningProgress(
            total=len(signals),
            completed=len(signals),
            recent_topics=topics,
        )
