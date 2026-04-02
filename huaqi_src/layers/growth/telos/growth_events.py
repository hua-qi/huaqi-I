import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from huaqi_src.config.adapters.storage import SQLiteStorageAdapter

_SCHEMA = """
CREATE TABLE IF NOT EXISTS growth_events (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    dimension       TEXT NOT NULL,
    layer           TEXT NOT NULL,
    title           TEXT NOT NULL,
    narrative       TEXT NOT NULL,
    old_content     TEXT,
    new_content     TEXT NOT NULL,
    trigger_signals TEXT NOT NULL,
    occurred_at     TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_growth_user_occurred  ON growth_events(user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_growth_user_dimension ON growth_events(user_id, dimension);
CREATE INDEX IF NOT EXISTS idx_growth_user_layer     ON growth_events(user_id, layer);
"""


class GrowthEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    dimension: str
    layer: str
    title: str
    narrative: str
    old_content: Optional[str] = None
    new_content: str
    trigger_signals: List[str] = Field(default_factory=list)
    occurred_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title must not be empty")
        return v

    @field_validator("narrative")
    @classmethod
    def narrative_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("narrative must not be empty")
        return v


def _row_to_event(row: sqlite3.Row) -> GrowthEvent:
    d = dict(row)
    d["trigger_signals"] = json.loads(d["trigger_signals"])
    return GrowthEvent(**{k: v for k, v in d.items() if k != "created_at"})


class GrowthEventStore:

    def __init__(self, adapter: SQLiteStorageAdapter) -> None:
        self._adapter = adapter
        self._init_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._adapter._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_table(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def save(self, event: GrowthEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO growth_events
                (id, user_id, dimension, layer, title, narrative,
                 old_content, new_content, trigger_signals, occurred_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.user_id,
                    event.dimension,
                    event.layer,
                    event.title,
                    event.narrative,
                    event.old_content,
                    event.new_content,
                    json.dumps(event.trigger_signals, ensure_ascii=False),
                    event.occurred_at.isoformat(),
                    event.created_at.isoformat(),
                ),
            )

    def get(self, event_id: str) -> Optional[GrowthEvent]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM growth_events WHERE id = ?", (event_id,)
            ).fetchone()
        return _row_to_event(row) if row else None

    def list_by_user(
        self,
        user_id: str,
        dimension: Optional[str] = None,
        limit: int = 50,
    ) -> List[GrowthEvent]:
        conditions = ["user_id = ?"]
        params: list = [user_id]
        if dimension:
            conditions.append("dimension = ?")
            params.append(dimension)
        sql = (
            f"SELECT * FROM growth_events WHERE {' AND '.join(conditions)} "
            f"ORDER BY occurred_at DESC LIMIT ?"
        )
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_event(r) for r in rows]
